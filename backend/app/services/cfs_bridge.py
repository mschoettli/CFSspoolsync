"""CFS / Moonraker Bridge — Version 2.

Parser für die echte Struktur der K2-Combo-Firmware:

    box.T1.temperature         → Kammer-Temperatur (Celsius)
    box.T1.dry_and_humidity    → Kammer-Feuchtigkeit (%)
    box.T1.material_type[0..3] → RFID-Material-Code pro Slot A/B/C/D
    box.T1.color_value[0..3]   → RFID-Farb-Hex pro Slot
    box.T1.remain_len[0..3]    → Verbleibende Filament-Länge in Prozent

Schreibt die erkannten Werte in zwei Tabellen:
  - CfsState: Kammer-Klima + Verbindungsstatus
  - CfsSlotSnapshot: was das CFS pro Slot aktuell sieht (für UI-Vorbefüllung)

Das Gewicht einer eingelegten Spule (current_weight in gramm) wird aus
dem verbleibenden Prozentwert relativ zum Snapshot bei Anlage berechnet.
"""
import asyncio
import math
import random
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models import CfsSlotSnapshot, CfsState, HistoryEntry, Slot, Spool
from ..ws import manager
from .material_codes import lookup_material, parse_color


class CfsBridge:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop = False
        self._last_history_write = 0.0

    async def start(self) -> None:
        self._stop = False
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    # ---------- Main loop ----------
    async def _run(self) -> None:
        await asyncio.sleep(1)
        while not self._stop:
            try:
                await self._tick()
            except Exception as exc:  # noqa: BLE001
                print(f"[cfs-bridge] tick error: {exc}", flush=True)
            await asyncio.sleep(1.0)

    async def _tick(self) -> None:
        db: Session = SessionLocal()
        try:
            cfs = db.query(CfsState).first() or CfsState(id=1)
            if cfs.id is None:
                db.add(cfs)
                db.commit()
                db.refresh(cfs)

            # ---------- 1. Moonraker / Simulator ----------
            if settings.moonraker_host:
                parsed = await self._poll_moonraker()
                if parsed is not None:
                    cfs.connected = True
                    cfs.temperature = parsed["temperature"]
                    cfs.humidity = parsed["humidity"]
                    self._write_snapshots(db, parsed["slots"])
                else:
                    cfs.connected = False
            else:
                # Simulator
                cfs.connected = True
                cfs.temperature = _clamp(
                    cfs.temperature + (random.random() - 0.5) * 0.3, 22, 34
                )
                cfs.humidity = _clamp(
                    cfs.humidity + (random.random() - 0.5) * 0.4, 10, 35
                )
                # Sim-Snapshots nur falls bisher alle leer sind (first start)
                any_populated = db.query(CfsSlotSnapshot).filter(
                    CfsSlotSnapshot.present == True  # noqa: E712
                ).first()
                if not any_populated:
                    self._write_snapshots(db, _fake_snapshots())

            cfs.last_sync = datetime.utcnow()

            # ---------- 2. Slot-Gewichte live aktualisieren ----------
            self._update_slot_weights(db)

            # ---------- 3. Print simulation ----------
            slots = db.query(Slot).order_by(Slot.id).all()
            now_ts = datetime.utcnow().timestamp()
            for slot in slots:
                if slot.is_printing and slot.spool_id and slot.current_weight > 0:
                    flow = settings.simulator_flow_gps + math.sin(now_ts / 2) * 0.6
                    slot.flow = round(flow, 2)
                    slot.current_weight = max(0.0, slot.current_weight - flow / 10.0)
                    if slot.current_weight <= 0:
                        slot.is_printing = False
                        slot.flow = 0
                else:
                    slot.flow = 0

            db.commit()

            # ---------- 4. History (alle 60s) ----------
            if now_ts - self._last_history_write >= 60:
                self._last_history_write = now_ts
                for slot in slots:
                    if slot.spool_id:
                        sp = db.query(Spool).get(slot.spool_id)
                        if sp:
                            net = max(0.0, slot.current_weight - sp.tare_weight)
                            db.add(HistoryEntry(
                                timestamp=datetime.utcnow(),
                                slot_id=slot.id,
                                spool_id=slot.spool_id,
                                net_weight=net,
                                consumed=slot.flow * 60 if slot.is_printing else 0,
                                temperature=cfs.temperature,
                                humidity=cfs.humidity,
                            ))
                db.commit()

            # ---------- 5. Broadcast ----------
            await manager.broadcast({
                "type": "live",
                "data": _serialize_live(cfs, slots, db),
            })
        finally:
            db.close()

    # ---------- Moonraker polling ----------
    async def _poll_moonraker(self) -> Optional[dict]:
        """Liest box.T1.* und extrahiert Kammer + 4 Slots."""
        url = (
            f"http://{settings.moonraker_host}:{settings.moonraker_port}"
            f"/printer/objects/query?box"
        )
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    return None
                payload = r.json().get("result", {}).get("status", {}).get("box", {})
        except (httpx.HTTPError, ValueError):
            return None

        if not payload:
            return None

        t1 = payload.get("T1", {})
        if not isinstance(t1, dict):
            return None

        temp = _to_float(t1.get("temperature"), 25.0)
        hum = _to_float(t1.get("dry_and_humidity"), 20.0)

        materials = t1.get("material_type") or []
        colors = t1.get("color_value") or []
        remains = t1.get("remain_len") or []

        slots = []
        for idx in range(4):
            slot_id = idx + 1
            mat_code = _safe_idx(materials, idx) or ""
            color_raw = _safe_idx(colors, idx) or ""
            remain_str = _safe_idx(remains, idx) or "-1"
            remain_pct = _to_float(remain_str, -1.0)

            mat_info = lookup_material(mat_code)
            has_rfid = mat_info is not None or (mat_code and mat_code != "-1")
            present = remain_pct >= 0

            slots.append({
                "slot_id": slot_id,
                "present": present,
                "material_code": mat_code if mat_code not in ("-1", "") else None,
                "manufacturer": (mat_info or {}).get("manufacturer"),
                "material": (mat_info or {}).get("material"),
                "nozzle_temp": (mat_info or {}).get("nozzle"),
                "bed_temp": (mat_info or {}).get("bed"),
                "color_hex": parse_color(color_raw) if color_raw else None,
                "remain_pct": remain_pct if present else None,
                "known": mat_info is not None,
            })

        return {
            "temperature": temp,
            "humidity": hum,
            "slots": slots,
        }

    # ---------- DB helpers ----------
    def _write_snapshots(self, db: Session, cfs_slots: list[dict]) -> None:
        """
        Persistiert den aktuellen CFS-Zustand pro Slot. Überschreibt immer
        genau 4 Rows (slot_id 1..4) damit kein Wachstum passiert.
        """
        for slot_data in cfs_slots:
            snap = db.query(CfsSlotSnapshot).get(slot_data["slot_id"])
            if snap is None:
                snap = CfsSlotSnapshot(slot_id=slot_data["slot_id"])
                db.add(snap)
            snap.present = slot_data["present"]
            snap.known = slot_data["known"]
            snap.material_code = slot_data["material_code"]
            snap.manufacturer = slot_data["manufacturer"]
            snap.material = slot_data["material"]
            snap.nozzle_temp = slot_data["nozzle_temp"]
            snap.bed_temp = slot_data["bed_temp"]
            snap.color_hex = slot_data["color_hex"]
            snap.remain_pct = slot_data["remain_pct"]
            snap.updated_at = datetime.utcnow()

    def _update_slot_weights(self, db: Session) -> None:
        """
        Aktualisiert `current_weight` pro Slot basierend auf aktuellem CFS-
        Remain-Prozentwert relativ zum Snapshot bei Spulen-Anlage.

        Formel:
            net_now = (remain_now / remain_at_creation) × (gross - tare)
            current_weight = net_now + tare
        """
        slots = db.query(Slot).order_by(Slot.id).all()
        for slot in slots:
            if not slot.spool_id or slot.is_printing:
                continue  # während Print-Simulation nicht überschreiben
            snap = db.query(CfsSlotSnapshot).get(slot.id)
            sp = db.query(Spool).get(slot.spool_id)
            if snap is None or sp is None:
                continue
            if snap.remain_pct is None or sp.initial_remain_pct is None:
                continue
            if sp.initial_remain_pct <= 0:
                continue

            net_initial = max(0.0, sp.gross_weight - sp.tare_weight)
            ratio = max(0.0, min(1.0, snap.remain_pct / sp.initial_remain_pct))
            net_now = net_initial * ratio
            slot.current_weight = round(sp.tare_weight + net_now, 2)


# ---------- Helpers ----------
def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _to_float(v, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_idx(lst, idx):
    if not isinstance(lst, list) or idx >= len(lst):
        return None
    return lst[idx]


def _fake_snapshots() -> list[dict]:
    """Demo-Snapshots für Simulator-Mode damit UI was zum Anzeigen hat."""
    return [
        {"slot_id": 1, "present": True,  "known": True,
         "material_code": "104001", "manufacturer": "Creality", "material": "Hyper PLA",
         "nozzle_temp": 210, "bed_temp": 60, "color_hex": "#F7B30F", "remain_pct": 78},
        {"slot_id": 2, "present": True,  "known": True,
         "material_code": "108001", "manufacturer": "Creality", "material": "CR-PLA",
         "nozzle_temp": 210, "bed_temp": 60, "color_hex": "#FFFFFF", "remain_pct": 34},
        {"slot_id": 3, "present": True,  "known": False,
         "material_code": "999999", "manufacturer": None, "material": None,
         "nozzle_temp": None, "bed_temp": None, "color_hex": "#1c1c1c", "remain_pct": 92},
        {"slot_id": 4, "present": False, "known": False,
         "material_code": None, "manufacturer": None, "material": None,
         "nozzle_temp": None, "bed_temp": None, "color_hex": None, "remain_pct": None},
    ]


def _serialize_live(cfs: CfsState, slots: list, db: Session) -> dict:
    slot_payload = []
    for s in slots:
        sp = db.query(Spool).get(s.spool_id) if s.spool_id else None
        snap = db.query(CfsSlotSnapshot).get(s.id)
        slot_payload.append({
            "id": s.id,
            "spool_id": s.spool_id,
            "current_weight": round(s.current_weight, 2),
            "is_printing": s.is_printing,
            "flow": s.flow,
            "spool": _spool_dict(sp) if sp else None,
            "cfs_snapshot": _snapshot_dict(snap) if snap else None,
        })
    return {
        "cfs": {
            "temperature": round(cfs.temperature, 1),
            "humidity": round(cfs.humidity, 1),
            "connected": cfs.connected,
            "last_sync": cfs.last_sync.isoformat(),
        },
        "slots": slot_payload,
    }


def _spool_dict(sp: Spool) -> dict:
    return {
        "id": sp.id,
        "manufacturer": sp.manufacturer, "material": sp.material,
        "color": sp.color, "color_hex": sp.color_hex,
        "diameter": sp.diameter,
        "nozzle_temp": sp.nozzle_temp, "bed_temp": sp.bed_temp,
        "gross_weight": sp.gross_weight, "tare_weight": sp.tare_weight,
        "initial_remain_pct": sp.initial_remain_pct,
        "name": sp.name,
    }


def _snapshot_dict(snap: CfsSlotSnapshot) -> dict:
    return {
        "slot_id": snap.slot_id,
        "present": snap.present, "known": snap.known,
        "material_code": snap.material_code,
        "manufacturer": snap.manufacturer, "material": snap.material,
        "nozzle_temp": snap.nozzle_temp, "bed_temp": snap.bed_temp,
        "color_hex": snap.color_hex,
        "remain_pct": snap.remain_pct,
    }


bridge = CfsBridge()
