from fastapi import APIRouter, Request

from app.db.session import SessionLocal
from app.models import Spool

router = APIRouter(prefix="/api/cfs", tags=["cfs"])


@router.get("")
async def cfs_overview(request: Request) -> dict:
    _version, snapshot = request.app.state.telemetry_hub.snapshot()
    cfs_live = snapshot.get("cfs", {}) if isinstance(snapshot, dict) else {}

    db = SessionLocal()
    try:
        active = {
            spool.cfs_slot: spool
            for spool in db.query(Spool).filter(Spool.status == "aktiv").all()
            if spool.cfs_slot in (1, 2, 3, 4)
        }
        slots = []
        for slot in (1, 2, 3, 4):
            spool = active.get(slot)
            live_slot = (cfs_live.get("slots", {}) or {}).get(slot, {}) if isinstance(cfs_live, dict) else {}
            slots.append(
                {
                    "slot": slot,
                    "key": f"Slot {slot}",
                    "is_active_slot": cfs_live.get("active_slot") == slot if isinstance(cfs_live, dict) else False,
                    "spool": (
                        {
                            "id": spool.id,
                            "material": spool.material,
                            "brand": spool.brand,
                            "color": spool.color,
                            "remaining_weight": spool.remaining_weight,
                            "initial_weight": spool.initial_weight,
                        }
                        if spool
                        else None
                    ),
                    "live": live_slot if isinstance(live_slot, dict) else {},
                }
            )

        return {
            "reachable": bool(cfs_live.get("reachable", False)) if isinstance(cfs_live, dict) else False,
            "degraded_reason": cfs_live.get("degraded_reason", "") if isinstance(cfs_live, dict) else "",
            "active_slot": cfs_live.get("active_slot") if isinstance(cfs_live, dict) else None,
            "temperature_c": ((cfs_live.get("climate", {}) or {}).get("temperature_c") if isinstance(cfs_live, dict) else None),
            "humidity_percent": ((cfs_live.get("climate", {}) or {}).get("humidity_percent") if isinstance(cfs_live, dict) else None),
            "slots": slots,
        }
    finally:
        db.close()
