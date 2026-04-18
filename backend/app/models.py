"""ORM-Modelle."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
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
    gross_weight = Column(Float, nullable=False)   # initiales Bruttogewicht (mit Spule)
    tare_weight = Column(Float, nullable=False)    # aufgelöste Tara bei Anlage
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
    current_weight = Column(Float, nullable=False, default=0)  # live Bruttogewicht
    is_printing = Column(Boolean, nullable=False, default=False)
    flow = Column(Float, nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    spool = relationship("Spool", back_populates="slot")


class CfsState(Base):
    """Singleton-Row mit aktuellem CFS-Umgebungszustand."""
    __tablename__ = "cfs_state"

    id = Column(Integer, primary_key=True, default=1)
    temperature = Column(Float, default=25.0)
    humidity = Column(Float, default=20.0)
    connected = Column(Boolean, default=False)
    last_sync = Column(DateTime, default=datetime.utcnow)


class HistoryEntry(Base):
    """Verbrauchs-Historie. Pro Minute ein Eintrag je aktivem Slot."""
    __tablename__ = "history"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    slot_id = Column(Integer, nullable=False)
    spool_id = Column(Integer, nullable=True)
    net_weight = Column(Float, nullable=False)    # aktuelles Netto
    consumed = Column(Float, nullable=False, default=0)  # seit letztem Eintrag verbraucht
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
