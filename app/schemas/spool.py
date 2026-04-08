"""Pydantic schemas for spool resources."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SpoolCreate(BaseModel):
    """Payload for creating a spool entry."""

    material: str = Field(min_length=1)
    color: str = "#888888"
    brand: str = ""
    name: str = ""
    nozzle_min: int = Field(default=190, ge=0, le=500)
    nozzle_max: int = Field(default=230, ge=0, le=500)
    bed_temp: int = Field(default=60, ge=0, le=150)
    initial_weight: float = Field(gt=0)
    remaining_weight: Optional[float] = Field(default=None, ge=0)
    diameter: float = Field(default=1.75, gt=0)
    density: float = Field(default=1.24, gt=0)
    serial_num: str = ""
    notes: str = ""

    @model_validator(mode="after")
    def validate_ranges(self) -> "SpoolCreate":
        """Validate cross-field spool constraints."""
        if self.nozzle_min > self.nozzle_max:
            raise ValueError("nozzle_min must be <= nozzle_max")
        if self.remaining_weight is not None and self.remaining_weight > self.initial_weight:
            raise ValueError("remaining_weight must be <= initial_weight")
        return self


class SpoolUpdate(BaseModel):
    """Payload for partial spool updates."""

    material: Optional[str] = None
    color: Optional[str] = None
    brand: Optional[str] = None
    name: Optional[str] = None
    nozzle_min: Optional[int] = Field(default=None, ge=0, le=500)
    nozzle_max: Optional[int] = Field(default=None, ge=0, le=500)
    bed_temp: Optional[int] = Field(default=None, ge=0, le=150)
    initial_weight: Optional[float] = Field(default=None, gt=0)
    remaining_weight: Optional[float] = Field(default=None, ge=0)
    status: Optional[str] = None
    notes: Optional[str] = None
    diameter: Optional[float] = Field(default=None, gt=0)
    density: Optional[float] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "SpoolUpdate":
        """Validate cross-field constraints when both values are present."""
        if (
            self.nozzle_min is not None
            and self.nozzle_max is not None
            and self.nozzle_min > self.nozzle_max
        ):
            raise ValueError("nozzle_min must be <= nozzle_max")
        if (
            self.remaining_weight is not None
            and self.initial_weight is not None
            and self.remaining_weight > self.initial_weight
        ):
            raise ValueError("remaining_weight must be <= initial_weight")
        return self


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
