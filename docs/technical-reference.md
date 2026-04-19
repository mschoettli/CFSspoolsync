# Technical Reference

This document contains the technical details for CFSspoolsync that were removed from the root README.

## Configuration

Personal values (printer IP/hostname, API keys, private endpoints) must be stored only in `.env`.
Do not hardcode personal values in tracked repository files.

### Required / Common `.env` Variables

| Variable | Example / Default | Notes |
|---|---|---|
| `REGISTRY` | `ghcr.io/mschoettli` | Image namespace |
| `TAG` | `latest` | Image tag |
| `HTTP_PORT` | `8088` | Frontend port |
| `CFS_MOONRAKER_HOST` | *(set printer IP)* | Set the printer IP for live K2 mode |
| `CFS_MOONRAKER_PORT` | `7125` | Moonraker API port |
| `TZ` | `Europe/Zurich` | Container timezone |
| `CFS_OPENAI_API_KEY` | *(optional)* | OCR cloud fallback |
| `CFS_ANTHROPIC_API_KEY` | *(optional)* | OCR cloud fallback |
| `CFS_OCR_ENABLE_CLOUD_FALLBACK` | `true` | Enable/disable cloud OCR normalization |

### Live Mode vs Simulator

- Live mode: set `CFS_MOONRAKER_HOST` to your K2 host/IP.
- Simulator mode: leave `CFS_MOONRAKER_HOST` empty.

## Deployment

### Standard (prebuilt images)

```bash
docker compose up -d
```

### Local build override

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

## API Overview (Active Stack)

All endpoints are under `/api`.

### Spools

- `GET /spools`
- `POST /spools`
- `GET /spools/{spool_id}`
- `PATCH /spools/{spool_id}`
- `DELETE /spools/{spool_id}`

### Tares

- `GET /tares`
- `POST /tares`
- `PATCH /tares/{tare_id}`
- `DELETE /tares/{tare_id}`

### Slots

- `GET /slots`
- `POST /slots/{slot_id}/assign`
- `POST /slots/{slot_id}/unassign`
- `GET /cfs/slots`
- `GET /cfs/slots/{slot_id}`

### CFS + History + OCR

- `GET /cfs`
- `GET /history?days=7&slot_id=1`
- `POST /ocr/scan`
- `GET /health`

### WebSocket

- `ws://<host>/ws`
- Broadcast payload type: `live`

## Architecture

- Backend: `backend/app/main.py` + `backend/app/routes/*`
- Live bridge: `backend/app/services/cfs_bridge.py`
- Frontend: `frontend/src/App.jsx` and `frontend/src/components/*`
- Persistence: SQLite at `/app/data/cfs.db` inside backend container

## Additional Docs

- [Development Guide](development.md)
- [Troubleshooting Guide](troubleshooting.md)
