# Architecture

## Overview

CFSspoolsync is a single-container web application for tracking filament spools in a Creality K2 CFS environment.

Core responsibilities:
- Persist spool and print-job data in SQLite.
- Read live CFS material state from the printer over SSH.
- Poll Moonraker to detect print lifecycle transitions.
- Provide a browser UI served by FastAPI static files.

## Runtime Components

- **FastAPI app (`app/main.py`)**
  - Initializes DB tables.
  - Registers API routers.
  - Runs lifespan hooks for Moonraker polling and HTTP client lifecycle.
- **Routers (`app/routers/`)**
  - `spools`: inventory CRUD.
  - `cfs`: slot mapping, live read, sync, assign/remove.
  - `printer`: printer telemetry summary.
  - `jobs`: print history.
  - `ocr`: image upload and OCR parsing.
- **Services (`app/services/`)**
  - `moonraker.py`: transition tracking (`printing -> complete/standby/error/cancelled`).
  - `ssh_client.py`: printer SSH access + CFS JSON parsing.
  - `label_ocr.py`: OCR image preprocessing and text parsing heuristics.
- **Persistence**
  - SQLAlchemy ORM models in `app/models.py`.
  - SQLite in WAL mode (`app/database.py`).

## Data Flow

### Spool lifecycle
1. User creates spool via `/api/spools`.
2. Spool starts in `lager` status.
3. User assigns spool to slot via `/api/cfs/slot/{slot}/assign/{spool_id}`.
4. Spool becomes `aktiv` and receives `cfs_slot`.
5. User removes spool from slot via `/api/cfs/slot/{slot}/remove`.

### Print tracking lifecycle
1. Background poll checks Moonraker every `MOONRAKER_POLL_INTERVAL` seconds.
2. Transition `not printing -> printing` creates a `print_jobs` snapshot.
3. Transition `printing -> final state` captures post-print CFS values.
4. Consumption is calculated from remain-length delta and applied to active spools.

### Live CFS sync
1. API calls SSH service to read raw printer JSON.
2. JSON is normalized per slot (material, color, temps, remaining grams).
3. `/api/cfs/sync` updates active spool weights in DB.

## Frontend Structure

- `app/static/app.js`: main UI orchestrator.
- `app/static/js/api.js`: centralized API calls.
- `app/static/js/state.js`: shared client state.
- `app/static/js/polling.js`: polling + visibility refresh.
- `app/static/style.css`: styling.
- `app/static/index.html`: shell and view containers.

## Reliability Notes

- Blocking SSH and OCR work is moved off the event loop with `asyncio.to_thread` in async endpoints/workers.
- Moonraker calls use a reused `httpx.AsyncClient` to reduce connection setup overhead.
- Docker image and Compose define health checks against `/api/printer/status`.
