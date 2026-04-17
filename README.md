# CFSspoolsync-v3

Greenfield restart for CFS spool sync and live print telemetry.

## Current scope completed
- Monorepo scaffold (`backend` + `frontend`)
- FastAPI + Postgres + Docker Compose wiring
- React + Vite build pipeline with Nginx static serving (production mode)
- Core APIs: `/health`, `/api/app-config`
- Live telemetry backbone: `/api/events/stream` + `/api/printer/status`
- CFS/Spools/Jobs/Tare/OCR/Camera API foundations
- Moonraker as telemetry source (no SSH in v3)
- Alembic-backed schema migrations on backend startup

## Run
1. Copy `.env.example` to `.env`
2. `docker compose up -d`
3. Frontend: `http://localhost:5173`
4. Backend: `http://localhost:8080`

## Update in Dockge
- `backend` and `frontend` are pull-based images from GHCR.
- Default tags:
- `ghcr.io/mschoettli/cfsspoolsync-backend:main`
- `ghcr.io/mschoettli/cfsspoolsync-frontend:main`
- In Dockge, clicking update/pull fetches new app images directly.
- If GHCR returns `unauthorized`, run `docker logout ghcr.io` once on the host and retry.
