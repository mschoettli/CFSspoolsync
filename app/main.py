import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Spool, PrintJob
from app.services import moonraker, ssh_client
from app.services.label_ocr import ocr_image, parse_label

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Create DB tables on startup
Base.metadata.create_all(bind=engine)


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(moonraker.polling_loop(app))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="CFSspoolsync", version="1.0.0", lifespan=lifespan)


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class SpoolCreate(BaseModel):
    material: str
    color: str = "#888888"
    brand: str = ""
    name: str = ""
    nozzle_min: int = 190
    nozzle_max: int = 230
    bed_temp: int = 60
    initial_weight: float
    remaining_weight: Optional[float] = None
    diameter: float = 1.75
    density: float = 1.24
    serial_num: str = ""
    notes: str = ""


class SpoolUpdate(BaseModel):
    material: Optional[str] = None
    color: Optional[str] = None
    brand: Optional[str] = None
    name: Optional[str] = None
    nozzle_min: Optional[int] = None
    nozzle_max: Optional[int] = None
    bed_temp: Optional[int] = None
    initial_weight: Optional[float] = None
    remaining_weight: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    diameter: Optional[float] = None
    density: Optional[float] = None


class SpoolOut(BaseModel):
    id: int
    material: str
    color: str
    brand: str
    name: str
    nozzle_min: int
    nozzle_max: int
    bed_temp: int
    initial_weight: float
    remaining_weight: float
    status: str
    cfs_slot: Optional[int]
    serial_num: str
    diameter: float
    density: float
    notes: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Spool endpoints ──────────────────────────────────────────────────────────

@app.get("/api/spools", response_model=List[SpoolOut])
def list_spools(
    status: Optional[str] = Query(None, description="lager|aktiv|leer"),
    db: Session = Depends(get_db),
):
    q = db.query(Spool)
    if status:
        q = q.filter(Spool.status == status)
    return q.order_by(Spool.updated_at.desc()).all()


@app.post("/api/spools", response_model=SpoolOut, status_code=201)
def create_spool(payload: SpoolCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    remaining = data.pop("remaining_weight") or data["initial_weight"]
    spool = Spool(**data, remaining_weight=remaining, status="lager")
    db.add(spool)
    db.commit()
    db.refresh(spool)
    return spool


@app.get("/api/spools/{spool_id}", response_model=SpoolOut)
def get_spool(spool_id: int, db: Session = Depends(get_db)):
    s = db.query(Spool).filter(Spool.id == spool_id).first()
    if not s:
        raise HTTPException(404, "Spule nicht gefunden")
    return s


@app.put("/api/spools/{spool_id}", response_model=SpoolOut)
def update_spool(spool_id: int, payload: SpoolUpdate, db: Session = Depends(get_db)):
    s = db.query(Spool).filter(Spool.id == spool_id).first()
    if not s:
        raise HTTPException(404, "Spule nicht gefunden")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(s, field, value)
    s.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(s)
    return s


@app.delete("/api/spools/{spool_id}")
def delete_spool(spool_id: int, db: Session = Depends(get_db)):
    s = db.query(Spool).filter(Spool.id == spool_id).first()
    if not s:
        raise HTTPException(404, "Spule nicht gefunden")
    if s.status == "aktiv":
        raise HTTPException(400, "Aktive Spule zuerst aus dem CFS entfernen")
    db.delete(s)
    db.commit()
    return {"ok": True}


# ─── CFS endpoints ────────────────────────────────────────────────────────────

@app.get("/api/cfs")
def get_cfs_state(db: Session = Depends(get_db)):
    """Current CFS state: DB spools per slot."""
    active = db.query(Spool).filter(Spool.status == "aktiv").all()
    slot_map = {s.cfs_slot: SpoolOut.model_validate(s).model_dump() for s in active if s.cfs_slot}

    return {
        "slots": [
            {
                "slot": i,
                "key": ["T1A", "T1B", "T1C", "T1D"][i - 1],
                "spool": slot_map.get(i),
            }
            for i in range(1, 5)
        ]
    }


@app.get("/api/cfs/live")
def get_cfs_live():
    """Read live CFS data from K2 via SSH."""
    slots = ssh_client.get_all_slots()
    reachable = any(v is not None for v in slots.values())
    return {"reachable": reachable, "slots": slots}


@app.post("/api/cfs/sync")
def sync_from_k2(db: Session = Depends(get_db)):
    """Read live CFS weights and update all active spools in DB.

    Useful after a print that wasn't tracked, or to re-calibrate weights
    from the K2's internal remainLen data.
    """
    slots = ssh_client.get_all_slots()
    if all(v is None for v in slots.values()):
        raise HTTPException(503, "K2 nicht erreichbar")

    updated = []
    for slot_num, slot_data in slots.items():
        if not slot_data or not slot_data.get("loaded"):
            continue

        spool = (
            db.query(Spool)
            .filter(Spool.cfs_slot == slot_num, Spool.status == "aktiv")
            .first()
        )
        if not spool:
            continue

        new_weight = round(
            ssh_client.meters_to_grams(
                slot_data["remain_len"], spool.diameter, spool.density
            ),
            1,
        )
        old_weight = spool.remaining_weight
        spool.remaining_weight = new_weight
        spool.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        updated.append({
            "slot": slot_num,
            "key": slot_data["key"],
            "spool_id": spool.id,
            "old_g": old_weight,
            "new_g": new_weight,
        })

    db.commit()
    return {"synced": len(updated), "updates": updated}


@app.get("/api/cfs/slot/{slot_num}/read")
def read_slot_live(slot_num: int):
    """Read one slot live from K2."""
    if slot_num not in (1, 2, 3, 4):
        raise HTTPException(400, "Slot muss 1–4 sein")
    data = ssh_client.get_slot(slot_num)
    if data is None:
        raise HTTPException(503, "K2 nicht erreichbar oder Slot leer")
    return data


@app.post("/api/cfs/slot/{slot_num}/assign/{spool_id}")
def assign_spool(slot_num: int, spool_id: int, db: Session = Depends(get_db)):
    """Move a spool from storage into a CFS slot."""
    if slot_num not in (1, 2, 3, 4):
        raise HTTPException(400, "Slot muss 1–4 sein")

    occupied = (
        db.query(Spool)
        .filter(Spool.cfs_slot == slot_num, Spool.status == "aktiv")
        .first()
    )
    if occupied:
        raise HTTPException(400, f"Slot {slot_num} ist bereits belegt (Spule #{occupied.id})")

    spool = db.query(Spool).filter(Spool.id == spool_id).first()
    if not spool:
        raise HTTPException(404, "Spule nicht gefunden")
    if spool.status != "lager":
        raise HTTPException(400, "Spule ist nicht im Lager")

    spool.cfs_slot = slot_num
    spool.status = "aktiv"
    spool.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"ok": True, "spool_id": spool_id, "slot": slot_num}


@app.post("/api/cfs/slot/{slot_num}/remove")
def remove_spool(slot_num: int, db: Session = Depends(get_db)):
    """Remove spool from a CFS slot back to storage."""
    spool = (
        db.query(Spool)
        .filter(Spool.cfs_slot == slot_num, Spool.status == "aktiv")
        .first()
    )
    if not spool:
        raise HTTPException(404, f"Kein aktiver Slot {slot_num}")

    spool.cfs_slot = None
    spool.status = "lager"
    spool.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"ok": True, "spool_id": spool.id}


# ─── Printer status ───────────────────────────────────────────────────────────

@app.get("/api/printer/status")
async def printer_status():
    status = await moonraker.get_printer_status()
    ps = status.get("print_stats", {})
    ext = status.get("extruder", {})
    bed = status.get("heater_bed", {})
    disp = status.get("display_status", {})

    return {
        "reachable": bool(status),
        "state": ps.get("state", "unknown"),
        "filename": ps.get("filename", ""),
        "progress": round(disp.get("progress", 0) * 100, 1),
        "extruder_temp": round(ext.get("temperature", 0), 1),
        "extruder_target": round(ext.get("target", 0), 1),
        "bed_temp": round(bed.get("temperature", 0), 1),
        "bed_target": round(bed.get("target", 0), 1),
    }


# ─── Print jobs ───────────────────────────────────────────────────────────────

@app.get("/api/jobs")
def list_jobs(limit: int = Query(30, le=100), db: Session = Depends(get_db)):
    jobs = (
        db.query(PrintJob)
        .order_by(PrintJob.started_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for j in jobs:
        consumed = 0.0
        for letter in "abcd":
            b = getattr(j, f"slot_{letter}_before")
            a = getattr(j, f"slot_{letter}_after")
            if b is not None and a is not None:
                consumed += b - a

        result.append(
            {
                "id": j.id,
                "filename": j.filename,
                "started_at": j.started_at,
                "finished_at": j.finished_at,
                "status": j.status,
                "total_consumed_g": round(consumed, 1),
                "slots": {
                    letter: {
                        "spool_id": getattr(j, f"slot_{letter}_spool_id"),
                        "before_g": getattr(j, f"slot_{letter}_before"),
                        "after_g": getattr(j, f"slot_{letter}_after"),
                    }
                    for letter in "abcd"
                },
            }
        )
    return result


@app.post("/api/scan-label")
async def scan_label(file: UploadFile = File(...)):
    """Upload a photo of a filament spool label and extract filament data via OCR."""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "Bild zu gross (max 10 MB)")

    text = ocr_image(content)
    if text is None:
        raise HTTPException(503, "OCR fehlgeschlagen – Tesseract nicht verfügbar")

    data = parse_label(text)
    return data


# ─── Static frontend (must be last) ──────────────────────────────────────────
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
