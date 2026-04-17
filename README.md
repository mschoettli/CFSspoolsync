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

The frontend container proxies `/api/*` internally to the backend service.
This means the UI works even when the browser cannot directly reach `:8080`.

`.env.default` is provided as a ready-to-use baseline for Dockge setups.

## Update in Dockge
- `backend` and `frontend` use pull-only images from GHCR.
- Image tag is controlled by one env key: `IMAGE_TAG` (default: `main`).
- Every push to `main` triggers `.github/workflows/publish-images.yml` and refreshes:
  - `ghcr.io/mschoettli/cfsspoolsync-backend:main`
  - `ghcr.io/mschoettli/cfsspoolsync-frontend:main`
- In Dockge, click `Update` to pull the refreshed `main` images.

### Dockge checklist (required)
1. Use this exact `docker-compose.yml` (no `build:` blocks for app services).
2. Set `IMAGE_TAG=main` in stack env.
   - Keep `VITE_API_BASE_URL` empty to use internal `/api` proxy mode.
3. Ensure both GHCR packages are `Public`:
   - `cfsspoolsync-backend`
   - `cfsspoolsync-frontend`
4. Verify the GitHub Action `Publish Docker Images` succeeded for the latest commit.
5. If host auth is stale, run once on the host: `docker logout ghcr.io`.
