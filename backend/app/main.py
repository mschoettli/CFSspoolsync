"""FastAPI Entry-Point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine
from .models import CfsSlotSnapshot, CfsState, Slot, Tare
from .routes import history as history_routes
from .routes import library as library_routes
from .routes import ocr as ocr_routes
from .routes import slots as slot_routes
from .routes import spools as spool_routes
from .routes import settings as settings_routes
from .routes import tares as tare_routes
from .seed import DEFAULT_TARES
from .services.cfs_bridge import bridge
from .ws import manager


def _seed_if_empty(db: Session) -> None:
    for i in range(1, 5):
        if not db.query(Slot).get(i):
            db.add(Slot(id=i))
        if not db.query(CfsSlotSnapshot).get(i):
            db.add(CfsSlotSnapshot(slot_id=i, present=False, known=False))

    existing_tares = {
        (row.manufacturer.strip().lower(), row.material.strip().lower())
        for row in db.query(Tare).all()
    }
    for t in DEFAULT_TARES:
        key = (t["manufacturer"].strip().lower(), t["material"].strip().lower())
        if key not in existing_tares:
            db.add(Tare(**t))
            existing_tares.add(key)

    if not db.query(CfsState).first():
        db.add(CfsState(id=1))

    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns()  # für Upgrades von v1 → v2
    db = SessionLocal()
    try:
        _seed_if_empty(db)
    finally:
        db.close()
    await bridge.start()
    yield
    await bridge.stop()


def _migrate_add_columns() -> None:
    """
    Rudimentäre Inline-Migration: SQLAlchemy create_all legt neue Tabellen an,
    aber fügt keine neuen Spalten zu bestehenden Tabellen hinzu. Wir prüfen
    daher explizit auf `spools.initial_remain_pct` und ergänzen bei Bedarf.

    Für komplexere Schemaänderungen sollte man zu Alembic wechseln; für eine
    einzelne neue Spalte reicht das.
    """
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "spools" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("spools")}
    if "initial_remain_pct" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE spools ADD COLUMN initial_remain_pct FLOAT"))
            print("[migration] added spools.initial_remain_pct", flush=True)


app = FastAPI(
    title="CFSspoolsync",
    description="Live-Tracker für das Creality CFS des K2 Combo",
    version="2.0.0",
    lifespan=lifespan,
)

origins = ["*"] if settings.cors_origins == "*" else settings.cors_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

prefix = settings.api_prefix
app.include_router(spool_routes.router, prefix=prefix)
app.include_router(tare_routes.router, prefix=prefix)
app.include_router(slot_routes.router, prefix=prefix)
app.include_router(slot_routes.cfs_slots_router, prefix=prefix)
app.include_router(history_routes.router, prefix=prefix)
app.include_router(history_routes.cfs_router, prefix=prefix)
app.include_router(settings_routes.router, prefix=prefix)
app.include_router(ocr_routes.router, prefix=prefix)
app.include_router(library_routes.router, prefix=prefix)


@app.get(f"{prefix}/health")
def health():
    return {
        "status": "ok",
        "simulator_mode": not bool(settings.moonraker_host),
        "moonraker_host": settings.moonraker_host or None,
        "version": "2.0.0",
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:
        await manager.disconnect(ws)
