"""Pydantic schemas for spool resources."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SpoolCreate(BaseModel):
    """Payload for creating a spool entry."""

    material: str
    color: str = "#888888"
    brand: str = ""
    name: str = ""
    nozzle_min: int = 190
    nozzle_max: int = 230
    bed_temp: int = 60
    initial_weight: float
    remaining_weight: Optional[float] = None
    diameter: float = 1.75
    density: float = 1.24
    serial_num: str = ""
    notes: str = ""


class SpoolUpdate(BaseModel):
    """Payload for partial spool updates."""

    material: Optional[str] = None
    color: Optional[str] = None
    brand: Optional[str] = None
    name: Optional[str] = None
    nozzle_min: Optional[int] = None
    nozzle_max: Optional[int] = None
    bed_temp: Optional[int] = None
    initial_weight: Optional[float] = None
    remaining_weight: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    diameter: Optional[float] = None
    density: Optional[float] = None


class SpoolOut(BaseModel):
    """Serialized spool response."""

    id: int
    material: str
    color: str
    brand: str
    name: str
    nozzle_min: int
    nozzle_max: int
    bed_temp: int
    initial_weight: float
    remaining_weight: float
    status: str
    cfs_slot: Optional[int]
    serial_num: str
    diameter: float
    density: float
    notes: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
