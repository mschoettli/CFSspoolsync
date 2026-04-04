from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.database import Base


class Spool(Base):
    __tablename__ = "spools"

    id = Column(Integer, primary_key=True, index=True)
    material = Column(String, nullable=False)
    color = Column(String, nullable=False, default="#888888")  # hex
    brand = Column(String, default="")
    name = Column(String, default="")
    nozzle_min = Column(Integer, default=190)
    nozzle_max = Column(Integer, default=230)
    bed_temp = Column(Integer, default=60)
    initial_weight = Column(Float, nullable=False)   # g
    remaining_weight = Column(Float, nullable=False)  # g
    status = Column(String, default="lager")         # lager / aktiv / leer
    cfs_slot = Column(Integer, nullable=True)         # 1–4 or NULL
    serial_num = Column(String, default="")
    diameter = Column(Float, default=1.75)            # mm
    density = Column(Float, default=1.24)             # g/cm³
    notes = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PrintJob(Base):
    __tablename__ = "print_jobs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, default="")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")  # running / finished / cancelled / error

    # Which spool was in which slot
    slot_a_spool_id = Column(Integer, nullable=True)
    slot_b_spool_id = Column(Integer, nullable=True)
    slot_c_spool_id = Column(Integer, nullable=True)
    slot_d_spool_id = Column(Integer, nullable=True)

    # Remaining weight (grams) before / after print
    slot_a_before = Column(Float, nullable=True)
    slot_a_after = Column(Float, nullable=True)
    slot_b_before = Column(Float, nullable=True)
    slot_b_after = Column(Float, nullable=True)
    slot_c_before = Column(Float, nullable=True)
    slot_c_after = Column(Float, nullable=True)
    slot_d_before = Column(Float, nullable=True)
    slot_d_after = Column(Float, nullable=True)

    # CFS remainLen (meters) snapshots
    snap_a_before = Column(Float, nullable=True)
    snap_b_before = Column(Float, nullable=True)
    snap_c_before = Column(Float, nullable=True)
    snap_d_before = Column(Float, nullable=True)
    snap_a_after = Column(Float, nullable=True)
    snap_b_after = Column(Float, nullable=True)
    snap_c_after = Column(Float, nullable=True)
    snap_d_after = Column(Float, nullable=True)
