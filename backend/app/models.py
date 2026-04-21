"""ORM-Modelle."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship

from .database import Base


class Spool(Base):
    __tablename__ = "spools"

    id = Column(Integer, primary_key=True)
    manufacturer = Column(String(100), nullable=False, index=True)
    material = Column(String(50), nullable=False, index=True)
    color = Column(String(100), nullable=False)
    color_hex = Column(String(16), nullable=False, default="#22c55e")
    diameter = Column(Float, nullable=False, default=1.75)
    nozzle_temp = Column(Integer, nullable=False, default=210)
    bed_temp = Column(Integer, nullable=False, default=60)
    gross_weight = Column(Float, nullable=False)
    tare_weight = Column(Float, nullable=False)
    # Snapshot of remaining percentage at spool creation time.
    # Used to compute current weight from live remaining percentage.
    initial_remain_pct = Column(Float, nullable=True)
    name = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    slot = relationship("Slot", back_populates="spool", uselist=False)


class Tare(Base):
    __tablename__ = "tares"

    id = Column(Integer, primary_key=True)
    manufacturer = Column(String(100), nullable=False, index=True)
    material = Column(String(50), nullable=False, index=True)
    weight = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Slot(Base):
    """Die 4 CFS-Slots. Immer genau 4 Rows, id = 1..4."""
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True)
    spool_id = Column(Integer, ForeignKey("spools.id", ondelete="SET NULL"), nullable=True)
    current_weight = Column(Float, nullable=False, default=0)
    is_printing = Column(Boolean, nullable=False, default=False)
    flow = Column(Float, nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    spool = relationship("Spool", back_populates="slot")


class CfsSlotSnapshot(Base):
    """
    Aktueller Roh-Zustand, wie das CFS den jeweiligen Slot sieht. Wird
    jede Sekunde vom Bridge-Service Ã¼berschrieben.

    UnabhÃ¤ngig davon ob User schon eine Spule im Spool-Lager angelegt hat.
    Dient als Daten-Quelle fÃ¼r Auto-Discovery und Modal-VorbefÃ¼llung.
    """
    __tablename__ = "cfs_slot_snapshots"

    slot_id = Column(Integer, primary_key=True)
    present = Column(Boolean, default=False)        # Physical spool is present
    known = Column(Boolean, default=False)          # Material code is known
    material_code = Column(String(20), nullable=True)
    manufacturer = Column(String(100), nullable=True)
    material = Column(String(50), nullable=True)
    nozzle_temp = Column(Integer, nullable=True)
    bed_temp = Column(Integer, nullable=True)
    color_hex = Column(String(16), nullable=True)
    remain_pct = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CfsState(Base):
    """Singleton-Row mit aktuellem CFS-Umgebungszustand."""
    __tablename__ = "cfs_state"

    id = Column(Integer, primary_key=True, default=1)
    temperature = Column(Float, default=25.0)
    humidity = Column(Float, default=20.0)
    connected = Column(Boolean, default=False)
    last_sync = Column(DateTime, default=datetime.utcnow)


class HistoryEntry(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    slot_id = Column(Integer, nullable=False)
    spool_id = Column(Integer, nullable=True)
    net_weight = Column(Float, nullable=False)
    consumed = Column(Float, nullable=False, default=0)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)


class AppSetting(Base):
    """Simple key/value store for UI and integration settings."""
    __tablename__ = "app_settings"

    key = Column(String(120), primary_key=True)
    value = Column(String(2000), nullable=False, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

