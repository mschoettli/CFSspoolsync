"""Pydantic schemas for print job resources."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class JobSlotOut(BaseModel):
    """Consumption information for one CFS slot in a print job."""

    spool_id: Optional[int]
    before_g: Optional[float]
    after_g: Optional[float]


class JobOut(BaseModel):
    """Serialized print job response."""

    id: int
    filename: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    status: str
    total_consumed_g: float
    slots: dict[str, JobSlotOut]
