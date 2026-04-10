# Deployment

## Requirements

- Docker Engine + Docker Compose
- Network reachability from container host to K2 printer IP
- SSH key access to printer user (`K2_SSH_USER`, default `root`)
- Moonraker enabled on printer (`:7125`)

## Environment setup

```bash
cp .env.example .env
```

Key variables:
- `K2_HOST`
- `K2_SSH_USER`
- `K2_SSH_KEY`
- `MOONRAKER_URL`
- `CFS_JSON_PATH`
- `PORT`
- `DATABASE_URL`
- `MOONRAKER_POLL_INTERVAL`

## Option A: Prebuilt image

```bash
docker compose up -d
```

Uses `docker-compose.yml` and `ghcr.io/mschoettli/cfsspoolsync:latest`.

## Option B: Local build

```bash
docker compose -f docker-compose.build.yml up -d --build
```

## Health checks

Both image and Compose define health checks against:
- `GET /api/printer/status`

Check health:

```bash
docker compose ps
```

## Data persistence

- SQLite is stored in `./data` via volume mount.
- SSH private key is mounted read-only from `K2_SSH_KEY`.

## Troubleshooting

- **Container unhealthy**: inspect logs with `docker compose logs -f`.
- **K2 unreachable**: verify host/IP, firewall, SSH key, and Moonraker URL.
- **OCR errors**: confirm image quality and OCR runtime dependencies in container. The app
  runs local Tesseract first and can automatically fall back to OpenAI/Claude when
  `OCR_ENABLE_CLOUD_FALLBACK=1` and API keys are configured.
- **Permission issue on mounted key**: ensure host path exists and is readable.
