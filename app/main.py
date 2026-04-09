"""Application bootstrap for CFSspoolsync."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import cfs, jobs, ocr, printer, spools
from app.services.label_ocr_v2 import warmup_ocr_v2_background
from app.services import moonraker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Create DB tables on startup.
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Manage background worker lifecycle for Moonraker polling."""
    await moonraker.init_http_client()
    warmup_ocr_v2_background()

    task = None
    if os.getenv("DISABLE_MOONRAKER_POLLING", "0") != "1":
        task = asyncio.create_task(moonraker.polling_loop())

    try:
        yield
    finally:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await moonraker.close_http_client()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    application = FastAPI(title="CFSspoolsync", version="1.1.0", lifespan=lifespan)

    application.include_router(spools.router)
    application.include_router(cfs.router)
    application.include_router(printer.router)
    application.include_router(jobs.router)
    application.include_router(ocr.router)

    # Must be mounted last so API routes are not shadowed by static files.
    application.mount("/", StaticFiles(directory="app/static", html=True), name="static")
    return application


app = create_app()
