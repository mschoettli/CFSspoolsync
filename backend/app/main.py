from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import Base, engine
from app.routers import app_config, camera, cfs, events, health, jobs, ocr, printer, spools, tare_defaults
from app.services.telemetry import TelemetryHub, telemetry_polling_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    hub = TelemetryHub()
    app.state.telemetry_hub = hub
    task = asyncio.create_task(telemetry_polling_loop(hub, settings.telemetry_poll_seconds))
    app.state.telemetry_task = task
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(app_config.router)
app.include_router(printer.router)
app.include_router(events.router)
app.include_router(cfs.router)
app.include_router(spools.router)
app.include_router(jobs.router)
app.include_router(camera.router)
app.include_router(ocr.router)
app.include_router(tare_defaults.router)
