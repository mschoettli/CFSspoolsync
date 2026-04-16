import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def fetch_moonraker_status() -> dict[str, Any]:
    url = f"{settings.moonraker_url.rstrip('/')}/printer/objects/query?print_stats&display_status&extruder&heater_bed&toolhead"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            status = response.json().get("result", {}).get("status", {})
            print_stats = status.get("print_stats", {})
            display = status.get("display_status", {})
            extruder = status.get("extruder", {})
            bed = status.get("heater_bed", {})

            return {
                "reachable": True,
                "source": "moonraker",
                "state": str(print_stats.get("state", "unknown")),
                "filename": str(print_stats.get("filename", "")),
                "progress": round(float(display.get("progress", 0.0) or 0.0) * 100.0, 1),
                "print_duration_seconds": round(float(print_stats.get("print_duration", 0.0) or 0.0), 1),
                "filament_used_raw": max(0.0, float(print_stats.get("filament_used", 0.0) or 0.0)),
                "extruder_temp": round(float(extruder.get("temperature", 0.0) or 0.0), 1),
                "extruder_target": round(float(extruder.get("target", 0.0) or 0.0), 1),
                "bed_temp": round(float(bed.get("temperature", 0.0) or 0.0), 1),
                "bed_target": round(float(bed.get("target", 0.0) or 0.0), 1),
            }
    except Exception as exc:
        logger.warning("Moonraker unreachable: %s", exc)
        return {
            "reachable": False,
            "source": "moonraker",
            "state": "offline",
            "filename": "",
            "progress": 0.0,
            "print_duration_seconds": 0.0,
            "filament_used_raw": 0.0,
            "extruder_temp": 0.0,
            "extruder_target": 0.0,
            "bed_temp": 0.0,
            "bed_target": 0.0,
        }
