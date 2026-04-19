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
        self._last_moonraker_ok_ts = 0.0
        self._last_printing_state = False
        self._last_print_job = {
            "active": False,
            "title": "",
            "remaining_seconds": None,
        }
        self._last_active_slot: Optional[int] = None
        self._last_remain_pct: dict[int, float] = {}
        self._last_slot_weights: dict[int, float] = {}

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
            print_probe = {
                "reachable": False,
                "is_printing": False,
                "title": "",
                "remaining_seconds": None,
            }
            if settings.moonraker_host:
                parsed = await self._poll_moonraker()
                print_probe = await self._poll_moonraker_print_state()
                if parsed is not None:
                    cfs.connected = True
                    cfs.temperature = parsed["temperature"]
                    cfs.humidity = parsed["humidity"]
                    self._write_snapshots(db, parsed["slots"])
                    self._last_active_slot = self._detect_active_slot(parsed["slots"])
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
                print_probe = {
                    "reachable": True,
                    "is_printing": False,
                    "title": "",
                    "remaining_seconds": None,
                }

            cfs.last_sync = datetime.utcnow()

            # ---------- 2. Slot-Gewichte live aktualisieren ----------
            self._update_slot_weights(db)

            # ---------- 3. Automatic print status + live flow ----------
            slots = db.query(Slot).order_by(Slot.id).all()
            now_ts = datetime.utcnow().timestamp()
            is_printing = self._resolve_printing_state(print_probe, now_ts)
            print_job = self._resolve_print_job(print_probe, is_printing, now_ts)
            active_slot = self._choose_active_slot(db, slots) if is_printing else None
            for slot in slots:
                previous_weight = self._last_slot_weights.get(slot.id, float(slot.current_weight))
                current_weight = float(slot.current_weight)
                consumed_per_second = max(0.0, previous_weight - current_weight)
                slot.is_printing = bool(active_slot and slot.id == active_slot)
                slot.flow = round(consumed_per_second, 2) if slot.is_printing else 0.0
                self._last_slot_weights[slot.id] = current_weight

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
                                consumed=slot.flow * 60 if slot.is_printing else 0.0,
                                temperature=cfs.temperature,
                                humidity=cfs.humidity,
                            ))
                db.commit()

            # ---------- 5. Broadcast ----------
            await manager.broadcast({
                "type": "live",
                "data": _serialize_live(cfs, slots, db, print_job),
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

    async def _poll_moonraker_print_state(self) -> dict:
        """Read global Klipper print state from Moonraker."""
        url = (
            f"http://{settings.moonraker_host}:{settings.moonraker_port}"
            f"/printer/objects/query?print_stats"
        )
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return {
                        "reachable": False,
                        "is_printing": False,
                        "title": "",
                        "remaining_seconds": None,
                    }
                payload = response.json().get("result", {}).get("status", {}).get("print_stats", {})
        except (httpx.HTTPError, ValueError):
            return {
                "reachable": False,
                "is_printing": False,
                "title": "",
                "remaining_seconds": None,
            }

        state = str(payload.get("state", "")).strip().lower()
        print_duration = max(0.0, _to_float(payload.get("print_duration"), 0.0))
        total_duration = _to_float(payload.get("total_duration"), -1.0)
        remaining_seconds: Optional[int] = None
        if total_duration > 0 and total_duration >= print_duration:
            remaining_seconds = int(total_duration - print_duration)

        return {
            "reachable": True,
            "is_printing": state == "printing",
            "title": _normalize_print_title(payload.get("filename")),
            "remaining_seconds": remaining_seconds,
        }

    def _resolve_printing_state(self, probe: dict, now_ts: float) -> bool:
        """Keep the last print state for a short grace window."""
        if probe.get("reachable"):
            self._last_moonraker_ok_ts = now_ts
            self._last_printing_state = bool(probe.get("is_printing"))
            return self._last_printing_state
        if now_ts - self._last_moonraker_ok_ts <= settings.moonraker_print_grace_s:
            return self._last_printing_state
        self._last_printing_state = False
        return False

    def _resolve_print_job(self, probe: dict, is_printing: bool, now_ts: float) -> dict:
        """Keep last print metadata through moonraker grace outages."""
        if probe.get("reachable"):
            self._last_print_job = {
                "active": bool(is_printing),
                "title": str(probe.get("title", "") or ""),
                "remaining_seconds": probe.get("remaining_seconds"),
            }
            return dict(self._last_print_job)

        if now_ts - self._last_moonraker_ok_ts <= settings.moonraker_print_grace_s:
            cached = dict(self._last_print_job)
            cached["active"] = bool(is_printing)
            return cached

        self._last_print_job = {
            "active": False,
            "title": "",
            "remaining_seconds": None,
        }
        return dict(self._last_print_job)

    def _detect_active_slot(self, cfs_slots: list[dict]) -> Optional[int]:
        """Infer active slot from the strongest negative remain_pct delta."""
        deltas: list[tuple[float, int]] = []
        current_remains: dict[int, float] = {}
        for slot in cfs_slots:
            slot_id = int(slot["slot_id"])
            remain_pct = slot.get("remain_pct")
            if remain_pct is None:
                continue
            remain_value = float(remain_pct)
            current_remains[slot_id] = remain_value
            if slot_id in self._last_remain_pct:
                deltas.append((remain_value - self._last_remain_pct[slot_id], slot_id))

        self._last_remain_pct = current_remains
        if deltas:
            most_negative = min(deltas, key=lambda item: item[0])
            if most_negative[0] < -0.01:
                return most_negative[1]
        return self._last_active_slot

    def _choose_active_slot(self, db: Session, slots: list[Slot]) -> Optional[int]:
        """Resolve a printing slot using detected slot and safe fallbacks."""
        candidate_ids = {slot.id for slot in slots if slot.spool_id}
        if self._last_active_slot in candidate_ids:
            return self._last_active_slot

        present_with_spool: list[int] = []
        for slot in slots:
            if not slot.spool_id:
                continue
            snapshot = db.query(CfsSlotSnapshot).get(slot.id)
            if snapshot and snapshot.present:
                present_with_spool.append(slot.id)

        if len(present_with_spool) == 1:
            self._last_active_slot = present_with_spool[0]
            return self._last_active_slot
        return None

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
        Aktualisiert `current_weight` pro Slot basierend auf CFS-RFID-Restwert.

        Einige Firmware-Staende liefern `remain_len` als echtes Prozent (0..100),
        andere als relative Länge/Baseline (>100). Daher:
          - <= 100  -> als Prozent interpretieren
          - > 100   -> relativ zu `initial_remain_pct` skalieren
                     (wird bei Bedarf aus erstem Live-Wert initialisiert)

        Formel:
            net_now = ratio × (gross - tare)
            current_weight = net_now + tare
        """
        slots = db.query(Slot).order_by(Slot.id).all()
        for slot in slots:
            if not slot.spool_id:
                continue
            snap = db.query(CfsSlotSnapshot).get(slot.id)
            sp = db.query(Spool).get(slot.spool_id)
            if snap is None or sp is None:
                continue
            if snap.remain_pct is None:
                continue

            net_initial = max(0.0, sp.gross_weight - sp.tare_weight)
            remain_value = float(snap.remain_pct)
            if remain_value <= 100.0:
                ratio = remain_value / 100.0
            else:
                if sp.initial_remain_pct is None or sp.initial_remain_pct <= 0:
                    sp.initial_remain_pct = remain_value
                ratio = remain_value / float(sp.initial_remain_pct)
            ratio = max(0.0, min(1.0, ratio))
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


def _normalize_print_title(raw_filename) -> str:
    filename = str(raw_filename or "").strip()
    if not filename:
        return ""
    return filename.replace("\\", "/").split("/")[-1]


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


def _serialize_live(cfs: CfsState, slots: list, db: Session, print_job: dict) -> dict:
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
            "print_job": {
                "active": bool(print_job.get("active")),
                "title": str(print_job.get("title", "") or ""),
                "remaining_seconds": print_job.get("remaining_seconds"),
            },
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

