"""CFS / Moonraker Bridge â€” Version 2.

Parser fÃ¼r die echte Struktur der K2-Combo-Firmware:

    box.T1.temperature         â†’ Kammer-Temperatur (Celsius)
    box.T1.dry_and_humidity    â†’ Kammer-Feuchtigkeit (%)
    box.T1.material_type[0..3] â†’ RFID-Material-Code pro Slot A/B/C/D
    box.T1.color_value[0..3]   â†’ RFID-Farb-Hex pro Slot
    box.T1.remain_len[0..3]    â†’ Verbleibende Filament-LÃ¤nge in Prozent

Schreibt die erkannten Werte in zwei Tabellen:
  - CfsState: Kammer-Klima + Verbindungsstatus
  - CfsSlotSnapshot: was das CFS pro Slot aktuell sieht (fÃ¼r UI-VorbefÃ¼llung)

Das Gewicht einer eingelegten Spule (current_weight in gramm) wird aus
dem verbleibenden Prozentwert relativ zum Snapshot bei Anlage berechnet.
"""
import asyncio
import random
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models import CfsSlotSnapshot, CfsState, HistoryEntry, Slot, Spool
from ..ws import manager
from .material_codes import lookup_material, parse_color
from .conversion import grams_from_mm


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
            "total_seconds": None,
        }
        self._last_active_slot: Optional[int] = None
        self._last_remain_pct: dict[int, float] = {}
        self._last_active_signal_ts: float = 0.0
        self._last_filament_used_raw: Optional[float] = None
        self._last_cycle_was_printing: bool = False
        self._last_cycle_active_slot: Optional[int] = None
        self._eta_last_file: str = ""
        self._eta_last_remaining: Optional[float] = None
        self._eta_last_total: Optional[float] = None
        self._eta_last_ts: float = 0.0
        self._estimated_time_cache: dict[str, float] = {}

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
            await asyncio.sleep(max(1.0, float(settings.consumption_tick_s)))

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
                "total_seconds": None,
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
                # Sim snapshots only if all are still empty (first start)
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
                    "total_seconds": None,
                }

            cfs.last_sync = datetime.utcnow()

            # ---------- 2. Resolve print state ----------
            slots = db.query(Slot).order_by(Slot.id).all()
            now_ts = datetime.utcnow().timestamp()
            is_printing = self._resolve_printing_state(print_probe, now_ts)
            if not is_printing and self._last_active_slot and (now_ts - self._last_active_signal_ts <= 30):
                # Moonraker print_stats can occasionally flap. Keep "printing" alive shortly
                # when we still receive strong CFS slot activity signals.
                is_printing = True
            print_job = self._resolve_print_job(print_probe, is_printing, now_ts)
            active_slot = self._choose_active_slot(db, slots) if is_printing else None

            # ---------- 3. Update slot weights live ----------
            self._sync_assigned_spools_from_rfid(db)
            self._update_slot_weights(db, skip_slot_id=active_slot if is_printing else None)
            consumed_g = self._apply_live_consumption_from_print_stats(db, slots, print_probe, is_printing, active_slot)

            if self._last_cycle_was_printing and not is_printing:
                self._persist_finished_print_weight(db, slots)

            for slot in slots:
                slot.is_printing = bool(active_slot and slot.id == active_slot)
                slot.flow = round(consumed_g / max(1.0, float(settings.consumption_tick_s)), 3) if slot.is_printing else 0.0

            db.commit()
            self._last_cycle_was_printing = bool(is_printing)
            self._last_cycle_active_slot = active_slot

            # ---------- 4. History (every 60s) ----------
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

        materials = _to_list(t1.get("material_type"))
        colors = _to_list(t1.get("color_value"))
        remains = _to_list(t1.get("remain_len"))

        slots = []
        for idx in range(4):
            slot_id = idx + 1
            mat_code = str(_safe_idx(materials, idx) or "").strip()
            color_raw = str(_safe_idx(colors, idx) or "").strip()
            remain_raw = _safe_idx(remains, idx)
            remain_pct = _to_float(remain_raw, -1.0)

            mat_info = lookup_material(mat_code)
            has_rfid = mat_info is not None or (mat_code and mat_code not in ("-1", "0", "None"))
            has_color = bool(color_raw and color_raw not in ("-1", "0", "None"))
            # Some firmware variants report -1 for remain_len even when a spool is present.
            # Treat slot as present if any strong RFID signal is available.
            present = (remain_pct >= 0) or has_rfid or has_color

            slots.append({
                "slot_id": slot_id,
                "present": present,
                "material_code": mat_code if mat_code not in ("-1", "") else None,
                "manufacturer": (mat_info or {}).get("manufacturer"),
                "material": (mat_info or {}).get("material"),
                "nozzle_temp": (mat_info or {}).get("nozzle"),
                "bed_temp": (mat_info or {}).get("bed"),
                "color_hex": parse_color(color_raw) if color_raw else None,
                "remain_pct": remain_pct if remain_pct >= 0 else None,
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
            f"/printer/objects/query?print_stats&virtual_sdcard"
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
                        "total_seconds": None,
                    }
                status = response.json().get("result", {}).get("status", {})
                payload = status.get("print_stats", {})
                virtual_sd = status.get("virtual_sdcard", {})
        except (httpx.HTTPError, ValueError):
            return {
                "reachable": False,
                "is_printing": False,
                "title": "",
                "remaining_seconds": None,
                "total_seconds": None,
            }

        state = str(payload.get("state", "")).strip().lower()
        filename = _normalize_print_title(payload.get("filename"))
        print_duration = max(0.0, _to_float(payload.get("print_duration"), 0.0))
        total_duration = _to_float(payload.get("total_duration"), -1.0)
        progress = _to_float(virtual_sd.get("progress"), -1.0)
        estimated_meta = await self._get_estimated_seconds_from_metadata(filename)

        progress_total = None
        if progress > 0 and progress <= 1:
            progress_total = print_duration / progress

        hybrid_total: Optional[float] = None
        if estimated_meta and progress_total:
            # Hybrid from slicer estimate + live progress projection.
            hybrid_total = (estimated_meta * 0.7) + (progress_total * 0.3)
        elif estimated_meta:
            hybrid_total = estimated_meta
        elif progress_total:
            hybrid_total = progress_total
        elif total_duration > 0:
            hybrid_total = total_duration

        total_seconds, remaining_seconds = self._smooth_eta(
            filename=filename,
            total_seconds=hybrid_total,
            elapsed_seconds=print_duration,
            is_printing=(state == "printing"),
        )

        return {
            "reachable": True,
            "is_printing": state == "printing",
            "title": filename,
            "remaining_seconds": remaining_seconds,
            "total_seconds": total_seconds,
            "filament_used_raw": _to_float(payload.get("filament_used"), 0.0),
        }

    async def _get_estimated_seconds_from_metadata(self, filename: str) -> Optional[float]:
        if not filename:
            return None
        cached = self._estimated_time_cache.get(filename)
        if cached is not None:
            return cached
        url = (
            f"http://{settings.moonraker_host}:{settings.moonraker_port}"
            f"/server/files/metadata?filename={quote(filename, safe='/')}"
        )
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return None
                result = response.json().get("result", {})
        except (httpx.HTTPError, ValueError):
            return None
        value = _to_float(result.get("estimated_time"), -1.0)
        if value > 0:
            self._estimated_time_cache[filename] = value
            return value
        return None

    def _smooth_eta(
        self,
        filename: str,
        total_seconds: Optional[float],
        elapsed_seconds: float,
        is_printing: bool,
    ) -> tuple[Optional[int], Optional[int]]:
        if not is_printing or not filename or total_seconds is None or total_seconds <= 0:
            self._eta_last_file = filename if is_printing else ""
            self._eta_last_remaining = None
            self._eta_last_total = None
            self._eta_last_ts = datetime.utcnow().timestamp()
            return None, None

        raw_remaining = max(0.0, total_seconds - elapsed_seconds)
        now_ts = datetime.utcnow().timestamp()
        if self._eta_last_file != filename:
            self._eta_last_file = filename
            self._eta_last_remaining = raw_remaining
            self._eta_last_total = total_seconds
            self._eta_last_ts = now_ts
            return int(max(elapsed_seconds, total_seconds)), int(raw_remaining)

        dt = max(1.0, now_ts - self._eta_last_ts)
        prev_remaining = self._eta_last_remaining if self._eta_last_remaining is not None else raw_remaining
        min_allowed = max(0.0, prev_remaining - dt * 2.0)
        max_allowed = prev_remaining + dt * 0.3
        smoothed_remaining = max(min_allowed, min(max_allowed, raw_remaining))
        smoothed_total = max(elapsed_seconds, smoothed_remaining + elapsed_seconds)

        self._eta_last_remaining = smoothed_remaining
        self._eta_last_total = smoothed_total
        self._eta_last_ts = now_ts
        return int(smoothed_total), int(smoothed_remaining)

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
                "total_seconds": probe.get("total_seconds"),
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
            "total_seconds": None,
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
                self._last_active_signal_ts = datetime.utcnow().timestamp()
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
        if len(candidate_ids) == 1:
            self._last_active_slot = next(iter(candidate_ids))
            return self._last_active_slot
        if present_with_spool:
            # Firmware can expose multiple "present" slots while only one prints.
            # Keep UI responsive by picking a deterministic fallback.
            self._last_active_slot = sorted(present_with_spool)[0]
            return self._last_active_slot
        if candidate_ids:
            self._last_active_slot = sorted(candidate_ids)[0]
            return self._last_active_slot
        return None

    # ---------- DB helpers ----------
    def _write_snapshots(self, db: Session, cfs_slots: list[dict]) -> None:
        """
        Persistiert den aktuellen CFS-Zustand pro Slot. Ãœberschreibt immer
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

    def _sync_assigned_spools_from_rfid(self, db: Session) -> None:
        """Keep technical fields in sync; manual brand/material wins."""
        slots = db.query(Slot).order_by(Slot.id).all()
        for slot in slots:
            if not slot.spool_id:
                continue
            snap = db.query(CfsSlotSnapshot).get(slot.id)
            spool = db.query(Spool).get(slot.spool_id)
            if snap is None or spool is None or not snap.present:
                continue

            if snap.color_hex:
                spool.color_hex = snap.color_hex
                spool.color = snap.color_hex
            if snap.nozzle_temp is not None:
                spool.nozzle_temp = int(snap.nozzle_temp)
            if snap.bed_temp is not None:
                spool.bed_temp = int(snap.bed_temp)

    def _update_slot_weights(self, db: Session, skip_slot_id: Optional[int] = None) -> None:
        """
        Aktualisiert `current_weight` pro Slot basierend auf CFS-RFID-Restwert.

        Einige Firmware-Staende liefern `remain_len` als echtes Prozent (0..100),
        andere als relative LÃ¤nge/Baseline (>100). Daher:
          - <= 100  -> als Prozent interpretieren
          - > 100   -> relativ zu `initial_remain_pct` skalieren
                     (wird bei Bedarf aus erstem Live-Wert initialisiert)

        Formel:
            net_now = ratio Ã— (gross - tare)
            current_weight = net_now + tare
        """
        slots = db.query(Slot).order_by(Slot.id).all()
        for slot in slots:
            if skip_slot_id and slot.id == skip_slot_id:
                continue
            if not slot.spool_id:
                continue
            if (getattr(slot, "weight_mode", "cfs_live") or "cfs_live") == "manual_fixed":
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

    def _apply_live_consumption_from_print_stats(
        self,
        db: Session,
        slots: list[Slot],
        print_probe: dict,
        is_printing: bool,
        active_slot_id: Optional[int],
    ) -> float:
        raw_now = print_probe.get("filament_used_raw")
        if raw_now is None:
            return 0.0
        raw_now = max(0.0, _to_float(raw_now, 0.0))

        if self._last_filament_used_raw is None:
            self._last_filament_used_raw = raw_now
            return 0.0

        delta_mm = raw_now - self._last_filament_used_raw
        self._last_filament_used_raw = raw_now

        if delta_mm <= 0:
            return 0.0
        if not is_printing:
            return 0.0

        max_delta_mm = max(0.0, float(settings.consumption_max_delta_mm))
        if max_delta_mm > 0:
            delta_mm = min(delta_mm, max_delta_mm)

        if not active_slot_id:
            return 0.0

        slot = next((item for item in slots if item.id == active_slot_id), None)
        if slot is None or not slot.spool_id:
            return 0.0
        if (getattr(slot, "weight_mode", "cfs_live") or "cfs_live") == "manual_fixed":
            return 0.0
        spool = db.query(Spool).get(slot.spool_id)
        if spool is None:
            return 0.0

        diameter = _to_float(getattr(spool, "diameter", None), float(settings.default_filament_diameter_mm))
        density = float(settings.default_filament_density)
        consumed_g = grams_from_mm(delta_mm, diameter, density)
        if consumed_g <= 0:
            return 0.0

        slot.current_weight = round(max(0.0, float(slot.current_weight) - consumed_g), 2)
        return consumed_g

    def _persist_finished_print_weight(self, db: Session, slots: list[Slot]) -> None:
        finished_slot_id = self._last_cycle_active_slot
        if not finished_slot_id:
            return
        slot = next((item for item in slots if item.id == finished_slot_id), None)
        if slot is None or not slot.spool_id:
            return
        spool = db.query(Spool).get(slot.spool_id)
        if spool is None:
            return
        spool.gross_weight = round(max(float(spool.tare_weight), float(slot.current_weight)), 2)


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


def _to_list(value):
    """Normalize telemetry values that may arrive as list, tuple, dict or CSV-like string."""
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        # Typical fallback: {"0": "...", "1": "..."} or {"A": "...", ...}
        out = []
        for key in ("0", "1", "2", "3", 0, 1, 2, 3, "A", "B", "C", "D", "a", "b", "c", "d"):
            if key in value:
                out.append(value[key])
        return out
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if "," in text:
            return [part.strip() for part in text.split(",")]
        return [text]
    return []


def _normalize_print_title(raw_filename) -> str:
    filename = str(raw_filename or "").strip()
    if not filename:
        return ""
    return filename.replace("\\", "/").split("/")[-1]


def _fake_snapshots() -> list[dict]:
    """Demo-Snapshots fÃ¼r Simulator-Mode damit UI was zum Anzeigen hat."""
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
            "weight_mode": getattr(s, "weight_mode", "cfs_live") or "cfs_live",
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
                "total_seconds": print_job.get("total_seconds"),
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


