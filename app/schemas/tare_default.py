"""Pydantic schemas for tare default resources."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.services.spool_defaults import normalize_brand


class TareDefaultCreate(BaseModel):
    """Payload for creating one tare default entry."""

    brand_label: str = Field(min_length=1)
    tare_weight_g: float = Field(ge=0)


class TareDefaultUpdate(BaseModel):
    """Payload for updating one tare default entry."""

    brand_label: str = Field(min_length=1)
    tare_weight_g: float = Field(ge=0)


class TareDefaultOut(BaseModel):
    """Serialized tare default response entry."""

    brand_key: str
    brand_label: str
    tare_weight_g: float
    is_system: bool
    updated_at: datetime | None

    @field_validator("brand_key")
    @classmethod
    def validate_brand_key(cls, value: str) -> str:
        """Ensure returned brand keys are normalized."""
        normalized = normalize_brand(value)
        if not normalized:
            raise ValueError("brand_key cannot be empty")
        return normalized
