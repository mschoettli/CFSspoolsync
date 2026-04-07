"""HTTP routes for printer telemetry."""

from fastapi import APIRouter

from app.schemas.printer import PrinterStatusOut
from app.services import moonraker

router = APIRouter(prefix="/api/printer", tags=["printer"])


@router.get("/status", response_model=PrinterStatusOut)
async def printer_status():
    """Return summarized printer status from Moonraker."""
    status = await moonraker.get_printer_status()
    print_stats = status.get("print_stats", {})
    extruder = status.get("extruder", {})
    bed = status.get("heater_bed", {})
    display = status.get("display_status", {})

    return {
        "reachable": bool(status),
        "state": print_stats.get("state", "unknown"),
        "filename": print_stats.get("filename", ""),
        "progress": round(display.get("progress", 0) * 100, 1),
        "extruder_temp": round(extruder.get("temperature", 0), 1),
        "extruder_target": round(extruder.get("target", 0), 1),
        "bed_temp": round(bed.get("temperature", 0), 1),
        "bed_target": round(bed.get("target", 0), 1),
    }
