"""Pydantic schemas for printer status responses."""

from typing import Optional

from pydantic import BaseModel


class PrinterStatusOut(BaseModel):
    """Current printer telemetry from Moonraker."""

    reachable: bool
    state: str
    filename: str
    progress: float
    extruder_temp: float
    extruder_target: float
    bed_temp: float
    bed_target: float
    remaining_seconds: Optional[float]
    current_layer: Optional[int] = None
    total_layer: Optional[int] = None
    print_duration_seconds: Optional[float] = None
    estimated_finish_at: Optional[str] = None
    cfs_temp: Optional[float] = None
    cfs_humidity: Optional[float] = None
