# CFSspoolsync

Filament management for Creality K2 Plus / K2 Combo with CFS.

![License](https://img.shields.io/badge/license-GPL%20v3-blue)
![Docker](https://img.shields.io/badge/docker-compose-blue)
![Python](https://img.shields.io/badge/python-3.12-blue)

## Features

- Live CFS slot view (4 slots) with material, color, and temperatures
- Storage management for all spools
- Print job history with per-slot consumption tracking
- SSH-based live sync from K2 CFS JSON
- OCR scan with local Tesseract and optional OpenAI/Claude cloud fallback

## Quick Start

1. Copy environment template:

```bash
cp .env.example .env
```

2. Edit `.env` values for your printer (`K2_HOST`, `K2_SSH_KEY_HOST`, `K2_SSH_KEY`, `MOONRAKER_URL`).
   - `K2_SSH_KEY_HOST`: absolute or project-relative key path on your Docker host.
   - `K2_SSH_KEY`: target path inside the container (default: `/root/.ssh/id_k2`).
   - OCR default profile:
     - `OCR_ENABLE_CLOUD_FALLBACK=1`
     - `OCR_PROVIDER_1=openai`, `OCR_PROVIDER_2=claude`
     - `OCR_TIMEOUT_SECONDS=60`
     - `OCR_CLOUD_TIMEOUT_SECONDS=6`
     - `OCR_TOTAL_BUDGET_SECONDS=30`
     - `OCR_HTTP_TIMEOUT_SECONDS=90`
     - Required for cloud fallback: `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY`

3. Start with prebuilt image:

```bash
docker compose up -d
```

Alternative local build:

```bash
docker compose -f docker-compose.build.yml up -d --build
```

The UI is available on `http://localhost:${PORT:-8080}`.

## Documentation

- [Architecture](docs/architecture.md)
- [Public API](docs/api.md)
- [Deployment](docs/deployment.md)
- [Development](docs/development.md)
- [K2 SSH Troubleshooting](docs/k2-ssh-troubleshooting.md)

## Tech Stack

- Backend: FastAPI + SQLAlchemy
- Database: SQLite (WAL mode)
- Frontend: Vanilla HTML/CSS/JS
- Runtime: Docker Compose

## License

GNU General Public License v3.0. See [LICENSE](LICENSE).
