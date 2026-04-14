"""HTTP routes for printer telemetry."""

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.schemas.printer import PrinterStatusOut
from app.services import moonraker, ssh_client

router = APIRouter(prefix="/api/printer", tags=["printer"])


def _to_float(value):
    """Safely coerce a numeric-like value to float.

    Args:
    -----
        value:
            Candidate value to convert.

    Returns:
    --------
        float | None:
            Converted value or ``None`` when conversion fails.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pick_env_metric(status: dict, metric: str):
    """Pick the best CFS/chamber metric from Moonraker object status.

    Args:
    -----
        status (dict):
            Moonraker status payload keyed by object name.
        metric (str):
            Metric name, for example ``temperature`` or ``humidity``.

    Returns:
    --------
        float | None:
            Best metric value for CFS/chamber sensors, if available.
    """
    candidates = []
    for name, payload in status.items():
        if not isinstance(payload, dict):
            continue

        lower = str(name).lower()
        if not any(token in lower for token in ("cfs", "ams", "chamber", "box", "cabinet")):
            continue

        value = _to_float(payload.get(metric))
        if value is None:
            continue

        if any(token in lower for token in ("cfs", "ams")):
            priority = 3
        elif any(token in lower for token in ("chamber", "box", "cabinet")):
            priority = 2
        else:
            priority = 1
        candidates.append((priority, value))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return round(candidates[0][1], 1)


@router.get("/status", response_model=PrinterStatusOut)
async def printer_status():
    """Return summarized printer status from Moonraker."""
    status = await moonraker.get_printer_status()
    print_stats = status.get("print_stats", {})
    extruder = status.get("extruder", {})
    bed = status.get("heater_bed", {})
    display = status.get("display_status", {})
    progress_raw = float(display.get("progress", 0) or 0)
    progress_pct = round(progress_raw * 100, 1)
    current_state = print_stats.get("state", "unknown")

    remaining_seconds = None
    elapsed_seconds = float(print_stats.get("print_duration", 0) or 0)
    if (
        current_state == "printing"
        and progress_raw > 0
        and elapsed_seconds > 0
    ):
        total_seconds = elapsed_seconds / progress_raw
        remaining_seconds = round(max(0.0, total_seconds - elapsed_seconds), 1)

    cfs_temp = _pick_env_metric(status, "temperature")
    cfs_humidity = _pick_env_metric(status, "humidity")
    layer_info = print_stats.get("info", {}) or {}
    current_layer = layer_info.get("current_layer")
    total_layer = layer_info.get("total_layer")
    estimated_finish_at = None
    if remaining_seconds is not None:
        finish_ts = datetime.now(timezone.utc) + timedelta(seconds=remaining_seconds)
        estimated_finish_at = finish_ts.isoformat()

    if cfs_temp is None or cfs_humidity is None:
        box_env = await asyncio.to_thread(ssh_client.get_box_environment)
        if cfs_temp is None:
            temp = _to_float(box_env.get("temperature"))
            cfs_temp = round(temp, 1) if temp is not None else None
        if cfs_humidity is None:
            humidity = _to_float(box_env.get("humidity"))
            cfs_humidity = round(humidity, 1) if humidity is not None else None

    current_layer_val = _to_float(current_layer)
    total_layer_val = _to_float(total_layer)
    await moonraker.ensure_live_consumption_tick(current_state)

    return {
        "reachable": bool(status),
        "state": current_state,
        "filename": print_stats.get("filename", ""),
        "progress": progress_pct,
        "extruder_temp": round(extruder.get("temperature", 0), 1),
        "extruder_target": round(extruder.get("target", 0), 1),
        "bed_temp": round(bed.get("temperature", 0), 1),
        "bed_target": round(bed.get("target", 0), 1),
        "remaining_seconds": remaining_seconds,
        "current_layer": int(current_layer_val) if current_layer_val is not None else None,
        "total_layer": int(total_layer_val) if total_layer_val is not None else None,
        "print_duration_seconds": round(elapsed_seconds, 1),
        "estimated_finish_at": estimated_finish_at,
        "cfs_temp": cfs_temp,
        "cfs_humidity": cfs_humidity,
    }
