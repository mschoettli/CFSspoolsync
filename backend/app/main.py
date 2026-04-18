"""FastAPI Entry-Point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine
from .models import CfsState, Slot, Tare
from .routes import history as history_routes
from .routes import slots as slot_routes
from .routes import spools as spool_routes
from .routes import tares as tare_routes
from .seed import DEFAULT_TARES
from .services.cfs_bridge import bridge
from .ws import manager


def _seed_if_empty(db: Session) -> None:
    """Erstinitialisierung: 4 Slots, Default-Tara-Tabelle, CFS-Row."""
    # 4 Slots garantieren
    for i in range(1, 5):
        if not db.query(Slot).get(i):
            db.add(Slot(id=i))

    # Tara-Defaults nur wenn komplett leer
    if db.query(Tare).count() == 0:
        for t in DEFAULT_TARES:
            db.add(Tare(**t))

    # CFS-Singleton
    if not db.query(CfsState).first():
        db.add(CfsState(id=1))

    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tabellen anlegen
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed_if_empty(db)
    finally:
        db.close()
    # CFS-Bridge starten
    await bridge.start()
    yield
    await bridge.stop()


app = FastAPI(
    title="CFS Filament Tracker",
    description="Live-Tracker für das Creality CFS des K2 Combo",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
origins = ["*"] if settings.cors_origins == "*" else settings.cors_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
prefix = settings.api_prefix
app.include_router(spool_routes.router, prefix=prefix)
app.include_router(tare_routes.router, prefix=prefix)
app.include_router(slot_routes.router, prefix=prefix)
app.include_router(history_routes.router, prefix=prefix)
app.include_router(history_routes.cfs_router, prefix=prefix)


@app.get(f"{prefix}/health")
def health():
    return {
        "status": "ok",
        "simulator_mode": not bool(settings.moonraker_host),
        "moonraker_host": settings.moonraker_host or None,
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Client kann Pings schicken, wir ignorieren sie inhaltlich
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:
        await manager.disconnect(ws)
