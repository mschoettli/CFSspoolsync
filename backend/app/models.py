from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Spool(Base):
    __tablename__ = "spools"

    id = Column(Integer, primary_key=True, index=True)
    material = Column(String, nullable=False)
    color = Column(String, nullable=False, default="#888888")
    brand = Column(String, default="")
    name = Column(String, default="")
    initial_weight = Column(Float, nullable=False)
    remaining_weight = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="lager")
    cfs_slot = Column(Integer, nullable=True)
    diameter = Column(Float, nullable=False, default=1.75)
    density = Column(Float, nullable=False, default=1.24)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class PrintJob(Base):
    __tablename__ = "print_jobs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, default="")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")

    filament_used_start_raw = Column(Float, nullable=True)
    filament_used_last_raw = Column(Float, nullable=True)

    live_consumed_mm = Column(Float, nullable=False, default=0.0)
    live_consumed_g = Column(Float, nullable=False, default=0.0)
    live_consumed_quality = Column(String, nullable=True)
    consumption_source = Column(String, nullable=True)

    slot_a_spool_id = Column(Integer, nullable=True)
    slot_b_spool_id = Column(Integer, nullable=True)
    slot_c_spool_id = Column(Integer, nullable=True)
    slot_d_spool_id = Column(Integer, nullable=True)

    slot_a_before = Column(Float, nullable=True)
    slot_a_after = Column(Float, nullable=True)
    slot_b_before = Column(Float, nullable=True)
    slot_b_after = Column(Float, nullable=True)
    slot_c_before = Column(Float, nullable=True)
    slot_c_after = Column(Float, nullable=True)
    slot_d_before = Column(Float, nullable=True)
    slot_d_after = Column(Float, nullable=True)


class TareDefault(Base):
    __tablename__ = "tare_defaults"

    id = Column(Integer, primary_key=True, index=True)
    brand_key = Column(String, nullable=False, unique=True, index=True)
    brand_label = Column(String, nullable=False)
    tare_weight_g = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
