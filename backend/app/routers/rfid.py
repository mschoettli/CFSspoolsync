import time

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/rfid", tags=["rfid"])


@router.post("/read")
async def read_rfid(
    request: Request,
    timeout_seconds: float = Query(5.0, ge=1.0, le=15.0),
) -> dict:
    """Read slot info from CFS telemetry as v1 RFID hook.

    Args:
    -----
        request (Request):
            FastAPI request with app state access.
        timeout_seconds (float):
            Maximum time to wait for an active slot signal.

    Returns:
    --------
        dict:
            RFID read result containing slot, material, and tag id.

    Raises:
    -------
        HTTPException:
            Raised when no active CFS slot is available within timeout.
    """
    hub = request.app.state.telemetry_hub
    deadline = time.time() + timeout_seconds
    last_version = -1

    while time.time() < deadline:
        version, snapshot = hub.snapshot()
        last_version = version
        cfs = snapshot.get("cfs", {}) if isinstance(snapshot, dict) else {}
        active_slot = cfs.get("active_slot") if isinstance(cfs, dict) else None
        if active_slot in (1, 2, 3, 4):
            slot_payload = (cfs.get("slots", {}) or {}).get(active_slot, {})
            material = ""
            if isinstance(slot_payload, dict):
                raw = slot_payload.get("raw", {})
                if isinstance(raw, dict):
                    material = str(
                        raw.get("material")
                        or raw.get("type")
                        or raw.get("filament_type")
                        or ""
                    ).strip()
            return {
                "ok": True,
                "slot": int(active_slot),
                "material": material,
                "tag_id": f"sim-{active_slot}-{int(time.time())}",
                "source": "telemetry-v1",
            }
        await hub.wait_for_update(last_version, timeout_seconds=0.7)

    raise HTTPException(status_code=504, detail="rfid_read_timeout_no_active_slot")
