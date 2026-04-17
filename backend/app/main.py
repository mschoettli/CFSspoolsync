from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import app_config, camera, cfs, events, health, jobs, ocr, printer, spools, tare_defaults
from app.services.telemetry import TelemetryHub, telemetry_polling_loop


def _cors_origins_from_settings(raw_origins: str) -> list[str]:
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return origins or ["http://localhost:5173"]


@asynccontextmanager
async def lifespan(app: FastAPI):
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
cors_origins = _cors_origins_from_settings(settings.cors_allow_origins)
allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
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
