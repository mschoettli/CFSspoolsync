# CFSspoolsync

CFSspoolsync is a web app for tracking Creality K2 Combo CFS slots, spool inventory, and filament consumption with live updates.

It combines:
- A FastAPI backend with SQLite persistence
- A React frontend with real-time updates over WebSocket
- OCR-assisted spool creation
- Docker Compose deployment with optional Watchtower auto-updates

<!-- screenshot: dashboard-overview -->

## Current Feature Set

- Live CFS environment data: temperature, humidity, connection status
- Four slot panels with:
  - Assigned spool details
  - Remaining weight derived from live CFS data
  - Automatic print-state display (Moonraker-driven, no manual print button)
- Inventory management:
  - Create, edit, delete spools
  - Assign/unassign to slots
  - Color name and HEX synchronization (`color` or `color_hex`)
- Tare management modal:
  - Community defaults + custom entries
  - Inline editing and dedicated add-entry modal
- History modal (24h / 7d / 30d) based on backend history records
- Settings modal:
  - Language toggle (DE/EN)
  - Theme toggle (dark/light)
  - Quick access to tare management
- OCR spool label scan:
  - Tesseract-based extraction
  - Optional OpenAI/Anthropic post-processing fallback (server-side only)

<!-- screenshot: settings-and-history -->
<!-- screenshot: tare-management-modal -->
<!-- screenshot: add-spool-ocr-modal -->

## K2 Slot Refresh Workflow (Important)

CFS data is polled continuously, but slot metadata and remaining values are only updated after the slot is re-read on the K2 UI.

On the K2 screen:
1. Open the CFS view.
2. Tap the colored spool.
3. Tap the slot refresh arrow above the slot.
4. Wait for the next backend poll cycle; values appear in the web app.

<!-- screenshot: slot-refresh-on-k2 -->

## Quick Start

```bash
git clone https://github.com/<your-user>/CFSspoolsync.git
cd CFSspoolsync
cp .env.example .env
# Edit .env (required)
docker compose up -d
```

Open:
- `http://<host>:8088` (or your configured `HTTP_PORT`)

## Configuration

Personal values (printer IP/hostname, API keys, private endpoints) must be stored only in `.env`.
Do not hardcode personal values in tracked repository files.

### Required / Common `.env` Variables

| Variable | Example / Default | Notes |
|---|---|---|
| `REGISTRY` | `ghcr.io/mschoettli` | Image namespace |
| `TAG` | `latest` | Image tag |
| `HTTP_PORT` | `8088` | Frontend port |
| `CFS_MOONRAKER_HOST` | *(set your own)* | Required for live K2 mode |
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

## Development

### Backend

```bash
cd backend
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
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

## Troubleshooting

See:
- [Troubleshooting Guide](docs/troubleshooting.md)

## License

MIT. See [LICENSE](LICENSE).
