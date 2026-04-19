"""Library export/import routes for spool inventory backup."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Spool, Tare
from ..schemas import (
    LibraryExportMeta,
    LibraryExportPayload,
    LibraryImportResult,
    LibrarySpoolItem,
    TareBase,
)

router = APIRouter(prefix="/library", tags=["library"])


def _normalize_text(value: str | None) -> str:
    """Return normalized lowercase text for key matching."""
    return (value or "").strip().lower()


def _normalize_float(value: float | None) -> float | None:
    """Normalize numeric values to stable precision for fingerprinting."""
    if value is None:
        return None
    return round(float(value), 4)


def _spool_fingerprint_from_payload(spool: LibrarySpoolItem) -> tuple:
    """Build a fingerprint tuple from import payload spool data."""
    return (
        _normalize_text(spool.manufacturer),
        _normalize_text(spool.material),
        _normalize_text(spool.color),
        (spool.color_hex or "").strip().upper(),
        _normalize_float(spool.diameter),
        int(spool.nozzle_temp),
        int(spool.bed_temp),
        _normalize_float(spool.gross_weight),
        _normalize_float(spool.tare_weight),
        _normalize_float(spool.initial_remain_pct),
        (spool.name or "").strip(),
    )


def _spool_fingerprint_from_model(spool: Spool) -> tuple:
    """Build a fingerprint tuple from database spool rows."""
    return (
        _normalize_text(spool.manufacturer),
        _normalize_text(spool.material),
        _normalize_text(spool.color),
        (spool.color_hex or "").strip().upper(),
        _normalize_float(spool.diameter),
        int(spool.nozzle_temp),
        int(spool.bed_temp),
        _normalize_float(spool.gross_weight),
        _normalize_float(spool.tare_weight),
        _normalize_float(spool.initial_remain_pct),
        (spool.name or "").strip(),
    )


@router.get("/export", response_model=LibraryExportPayload)
def export_library(db: Session = Depends(get_db)):
    """Export spool inventory and tare data as versioned JSON payload."""
    spools = db.query(Spool).order_by(Spool.id.asc()).all()
    tares = db.query(Tare).order_by(Tare.manufacturer.asc(), Tare.material.asc()).all()

    return {
        "meta": LibraryExportMeta(schema_version=1, exported_at=datetime.utcnow()),
        "spools": [
            LibrarySpoolItem(
                manufacturer=sp.manufacturer,
                material=sp.material,
                color=sp.color,
                color_hex=sp.color_hex,
                diameter=sp.diameter,
                nozzle_temp=sp.nozzle_temp,
                bed_temp=sp.bed_temp,
                gross_weight=sp.gross_weight,
                tare_weight=sp.tare_weight,
                initial_remain_pct=sp.initial_remain_pct,
                name=sp.name,
                created_at=sp.created_at,
                updated_at=sp.updated_at,
            )
            for sp in spools
        ],
        "tares": [
            TareBase(
                manufacturer=tr.manufacturer,
                material=tr.material,
                weight=tr.weight,
            )
            for tr in tares
        ],
    }


@router.post("/import", response_model=LibraryImportResult)
async def import_library(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import a previously exported JSON payload with merge semantics."""
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Please upload a JSON file.")

    try:
        raw_bytes = await file.read()
        payload_raw = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON file.") from exc

    try:
        payload = LibraryExportPayload.model_validate(payload_raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    if payload.meta.schema_version != 1:
        raise HTTPException(status_code=422, detail="Unsupported schema_version.")

    tares_created = 0
    tares_updated = 0
    spools_imported = 0

    try:
        existing_tares = {
            (_normalize_text(row.manufacturer), _normalize_text(row.material)): row
            for row in db.query(Tare).all()
        }

        for tare in payload.tares:
            key = (_normalize_text(tare.manufacturer), _normalize_text(tare.material))
            existing = existing_tares.get(key)
            if existing is None:
                new_tare = Tare(
                    manufacturer=tare.manufacturer.strip(),
                    material=tare.material.strip(),
                    weight=float(tare.weight),
                )
                db.add(new_tare)
                existing_tares[key] = new_tare
                tares_created += 1
            else:
                if float(existing.weight) != float(tare.weight):
                    existing.weight = float(tare.weight)
                    tares_updated += 1

        imported_counts: dict[tuple, int] = defaultdict(int)
        imported_exemplar: dict[tuple, LibrarySpoolItem] = {}
        for spool in payload.spools:
            fp = _spool_fingerprint_from_payload(spool)
            imported_counts[fp] += 1
            imported_exemplar.setdefault(fp, spool)

        existing_counts: dict[tuple, int] = defaultdict(int)
        for spool in db.query(Spool).all():
            existing_counts[_spool_fingerprint_from_model(spool)] += 1

        for fp, target_count in imported_counts.items():
            current_count = existing_counts.get(fp, 0)
            missing_count = max(0, target_count - current_count)
            if missing_count == 0:
                continue

            src = imported_exemplar[fp]
            for _ in range(missing_count):
                db.add(Spool(
                    manufacturer=src.manufacturer.strip(),
                    material=src.material.strip(),
                    color=(src.color or "").strip(),
                    color_hex=(src.color_hex or "").strip().upper(),
                    diameter=float(src.diameter),
                    nozzle_temp=int(src.nozzle_temp),
                    bed_temp=int(src.bed_temp),
                    gross_weight=float(src.gross_weight),
                    tare_weight=float(src.tare_weight),
                    initial_remain_pct=src.initial_remain_pct,
                    name=(src.name or "").strip(),
                ))
                spools_imported += 1

        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Import failed.") from exc

    return {
        "tares_created": tares_created,
        "tares_updated": tares_updated,
        "spools_imported": spools_imported,
        "errors": [],
    }
