"""Pydantic schemas for printer status responses."""

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
