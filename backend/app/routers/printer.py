from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/printer", tags=["printer"])


@router.get("/status")
async def printer_status(request: Request) -> dict:
    _version, snapshot = request.app.state.telemetry_hub.snapshot()
    printer = {
        "reachable": snapshot.get("reachable", False),
        "state": snapshot.get("state", "unknown"),
        "filename": snapshot.get("filename", ""),
        "progress": snapshot.get("progress", 0.0),
        "print_duration_seconds": snapshot.get("print_duration_seconds", 0.0),
        "filament_used_raw": snapshot.get("filament_used_raw", 0.0),
        "live_consumed_mm": snapshot.get("live_consumed_mm", 0.0),
        "live_consumed_g": snapshot.get("live_consumed_g", 0.0),
        "live_consumed_quality": snapshot.get("live_consumed_quality", "estimated"),
        "consumption_source": snapshot.get("consumption_source", "none"),
        "extruder_temp": snapshot.get("extruder_temp", 0.0),
        "extruder_target": snapshot.get("extruder_target", 0.0),
        "bed_temp": snapshot.get("bed_temp", 0.0),
        "bed_target": snapshot.get("bed_target", 0.0),
    }
    return printer
