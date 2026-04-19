"""Pydantic-Schemas für die JSON-API."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


# ---------- Spool ----------
class SpoolBase(BaseModel):
    manufacturer: str = Field(..., min_length=1, max_length=100)
    material: str = Field(..., min_length=1, max_length=50)
    color: Optional[str] = Field(None, max_length=100)
    color_hex: Optional[str] = Field(None, pattern=r"^$|^#[0-9a-fA-F]{6}$")
    diameter: float = Field(1.75, ge=1.0, le=4.0)
    nozzle_temp: int = Field(210, ge=150, le=350)
    bed_temp: int = Field(60, ge=0, le=150)
    gross_weight: float = Field(..., gt=0)
    tare_weight: float = Field(..., ge=0)
    initial_remain_pct: Optional[float] = Field(None, ge=0, le=100)
    name: str = ""

    @model_validator(mode="after")
    def validate_color_fields(self):
        """Ensure at least one color field is provided."""
        has_color = bool((self.color or "").strip())
        has_color_hex = bool((self.color_hex or "").strip())
        if not has_color and not has_color_hex:
            raise ValueError("Either 'color' or 'color_hex' must be provided.")
        return self


class SpoolCreate(SpoolBase):
    assign_to_slot: Optional[int] = Field(None, ge=1, le=4)


class SpoolUpdate(BaseModel):
    manufacturer: Optional[str] = None
    material: Optional[str] = None
    color: Optional[str] = None
    color_hex: Optional[str] = Field(None, pattern=r"^$|^#[0-9a-fA-F]{6}$")
    diameter: Optional[float] = None
    nozzle_temp: Optional[int] = None
    bed_temp: Optional[int] = None
    gross_weight: Optional[float] = None
    tare_weight: Optional[float] = None
    initial_remain_pct: Optional[float] = None
    name: Optional[str] = None


class SpoolOut(SpoolBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- Tare ----------
class TareBase(BaseModel):
    manufacturer: str = Field(..., min_length=1, max_length=100)
    material: str = Field(..., min_length=1, max_length=50)
    weight: float = Field(..., ge=0)


class TareCreate(TareBase):
    pass


class TareUpdate(BaseModel):
    manufacturer: Optional[str] = None
    material: Optional[str] = None
    weight: Optional[float] = None


class TareOut(TareBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# ---------- CFS Snapshot (Live-Erkennung pro Slot) ----------
class CfsSnapshotOut(BaseModel):
    slot_id: int
    present: bool
    known: bool
    material_code: Optional[str] = None
    manufacturer: Optional[str] = None
    material: Optional[str] = None
    nozzle_temp: Optional[int] = None
    bed_temp: Optional[int] = None
    color_hex: Optional[str] = None
    remain_pct: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)


# ---------- Slot ----------
class SlotOut(BaseModel):
    id: int
    spool_id: Optional[int]
    current_weight: float
    is_printing: bool
    flow: float
    spool: Optional[SpoolOut] = None
    cfs_snapshot: Optional[CfsSnapshotOut] = None
    model_config = ConfigDict(from_attributes=True)


class SlotAssign(BaseModel):
    spool_id: int


# ---------- CFS ----------
class CfsStateOut(BaseModel):
    temperature: float
    humidity: float
    connected: bool
    last_sync: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- History ----------
class HistoryOut(BaseModel):
    timestamp: datetime
    slot_id: int
    spool_id: Optional[int]
    net_weight: float
    consumed: float
    temperature: Optional[float]
    humidity: Optional[float]
    model_config = ConfigDict(from_attributes=True)
