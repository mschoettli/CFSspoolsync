"""CFS / Moonraker Bridge.

Pollt entweder den Moonraker-Endpunkt des K2 Combo und zieht Temperatur/
Feuchtigkeit + Spulen-Gewichte aus `printer.objects.query`, oder simuliert
realistisch wobbelnde Sensorwerte wenn kein CFS_MOONRAKER_HOST gesetzt ist.

Schreibt den aktuellen Zustand in die DB und broadcastet live an alle
verbundenen WebSocket-Clients.
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
from ..models import CfsState, Slot, Spool, HistoryEntry
from ..ws import manager


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
        # kleine Startverzögerung damit uvicorn oben ist
        await asyncio.sleep(1)
        tick_interval = 1.0
        while not self._stop:
            try:
                await self._tick()
            except Exception as exc:  # noqa: BLE001
                print(f"[cfs-bridge] tick error: {exc}", flush=True)
            await asyncio.sleep(tick_interval)

    async def _tick(self) -> None:
        """Wird jede Sekunde ausgeführt — pollt CFS, schreibt State, broadcastet."""
        db: Session = SessionLocal()
        try:
            cfs = db.query(CfsState).first()
            if cfs is None:
                cfs = CfsState(id=1)
                db.add(cfs)
                db.commit()
                db.refresh(cfs)

            # ---------- 1. Umgebungsdaten holen ----------
            if settings.moonraker_host:
                sensor_data = await self._poll_moonraker()
                if sensor_data is not None:
                    cfs.connected = True
                    cfs.temperature = sensor_data.get("temperature", cfs.temperature)
                    cfs.humidity = sensor_data.get("humidity", cfs.humidity)
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
            cfs.last_sync = datetime.utcnow()

            # ---------- 2. Slots updaten (Print-Verbrauch) ----------
            slots = db.query(Slot).order_by(Slot.id).all()
            now_ts = datetime.utcnow().timestamp()
            for slot in slots:
                if slot.is_printing and slot.spool_id and slot.current_weight > 0:
                    # sinusförmiger Flow um den Referenzwert
                    flow = settings.simulator_flow_gps + math.sin(now_ts / 2) * 0.6
                    slot.flow = round(flow, 2)
                    slot.current_weight = max(
                        0.0, slot.current_weight - flow / 10.0
                    )
                    if slot.current_weight <= 0:
                        slot.is_printing = False
                        slot.flow = 0
                else:
                    slot.flow = 0

            db.commit()

            # ---------- 3. History schreiben (alle 60s) ----------
            if now_ts - self._last_history_write >= 60:
                self._last_history_write = now_ts
                for slot in slots:
                    if slot.spool_id:
                        sp = db.query(Spool).get(slot.spool_id)
                        if sp:
                            net = max(0.0, slot.current_weight - sp.tare_weight)
                            entry = HistoryEntry(
                                timestamp=datetime.utcnow(),
                                slot_id=slot.id,
                                spool_id=slot.spool_id,
                                net_weight=net,
                                consumed=slot.flow * 60 if slot.is_printing else 0,
                                temperature=cfs.temperature,
                                humidity=cfs.humidity,
                            )
                            db.add(entry)
                db.commit()

            # ---------- 4. Broadcast ----------
            payload = _serialize_live(cfs, slots, db)
            await manager.broadcast({"type": "live", "data": payload})
        finally:
            db.close()

    # ---------- Moonraker poll ----------
    async def _poll_moonraker(self) -> Optional[dict]:
        """
        Pollt Moonraker `printer/objects/query` für CFS-Daten.

        Creality K2 Combo stellt die CFS-Daten über das Objekt
        `box` (Temperatur/Feuchtigkeit) und `extruder` / `filament_sensor`
        bereit. Je nach Firmware kann das Feld-Mapping abweichen; der
        unten stehende Parser fängt beide gängige Varianten ab.
        """
        url = (
            f"http://{settings.moonraker_host}:{settings.moonraker_port}"
            f"/printer/objects/query?box&extruder&cfs"
        )
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    return None
                data = r.json().get("result", {}).get("status", {})
        except (httpx.HTTPError, ValueError):
            return None

        box = data.get("box") or data.get("cfs") or {}
        return {
            "temperature": box.get("temperature") or box.get("temp") or 25.0,
            "humidity": box.get("humidity") or box.get("hum") or 20.0,
        }


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _serialize_live(cfs: CfsState, slots: list[Slot], db: Session) -> dict:
    slot_payload = []
    for s in slots:
        sp = db.query(Spool).get(s.spool_id) if s.spool_id else None
        slot_payload.append({
            "id": s.id,
            "spool_id": s.spool_id,
            "current_weight": round(s.current_weight, 2),
            "is_printing": s.is_printing,
            "flow": s.flow,
            "spool": _spool_dict(sp) if sp else None,
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
        "manufacturer": sp.manufacturer,
        "material": sp.material,
        "color": sp.color,
        "color_hex": sp.color_hex,
        "diameter": sp.diameter,
        "nozzle_temp": sp.nozzle_temp,
        "bed_temp": sp.bed_temp,
        "gross_weight": sp.gross_weight,
        "tare_weight": sp.tare_weight,
        "name": sp.name,
    }


bridge = CfsBridge()
