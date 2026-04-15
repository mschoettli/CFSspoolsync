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

### OCR default profile

Use exactly this default profile:

```env
OCR_ENABLE_CLOUD_FALLBACK=1
OCR_PROVIDER_1=openai
OCR_PROVIDER_2=claude
OCR_TIMEOUT_SECONDS=60
OCR_CLOUD_TIMEOUT_SECONDS=6
OCR_TOTAL_BUDGET_SECONDS=30
OCR_HTTP_TIMEOUT_SECONDS=90
OCR_CONFIDENCE_ACCEPTED=0.8
OCR_CONFIDENCE_LOW=0.55
OCR_MAX_VARIANTS=6
OCR_WARMUP=1
OCR_DEBUG=0
OPENAI_MODEL=gpt-4.1-mini
ANTHROPIC_MODEL=claude-3-5-sonnet-latest
```

Required credentials for cloud fallback:
- `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY`
- Without these keys, only local Tesseract is used and warnings are returned in OCR responses.

### What each OCR setting does

| Variable | Default | Meaning | Higher value effect | Lower value effect |
|---|---:|---|---|---|
| `OCR_ENABLE_CLOUD_FALLBACK` | `1` | Enables cloud retry after weak local OCR. | `1` increases recovery chance on difficult photos. | `0` is faster and fully local, but weaker on hard labels. |
| `OCR_PROVIDER_1` | `openai` | First cloud provider in fallback chain. | N/A (choice value). | N/A (choice value). |
| `OCR_PROVIDER_2` | `claude` | Second cloud provider in fallback chain. | N/A (choice value). | N/A (choice value). |
| `OCR_TIMEOUT_SECONDS` | `60` | Local OCR request budget passed to OCR service. | More time for local OCR, slower worst-case response. | Faster failover, but more partial local results. |
| `OCR_CLOUD_TIMEOUT_SECONDS` | `6` | Per-cloud-provider timeout cap. | Better chance for complete cloud result, slower fallback. | Faster return, more provider timeouts. |
| `OCR_TOTAL_BUDGET_SECONDS` | `30` | Hard overall OCR budget for local + cloud chain. | More complete pipeline attempts, longer waiting. | Faster response, more partial-timeout warnings. |
| `OCR_HTTP_TIMEOUT_SECONDS` | `90` | API route timeout for `/api/ocr/scan`. | Fewer HTTP timeouts, longer client wait. | Faster HTTP failure if OCR path is slow. |
| `OCR_CONFIDENCE_ACCEPTED` | `0.8` | Threshold for auto-accepted field values. | Safer autofill, fewer accepted fields. | More autofill, higher false-positive risk. |
| `OCR_CONFIDENCE_LOW` | `0.55` | Lower confidence boundary before reject. | More values become rejected. | More values flagged as low-confidence instead of rejected. |
| `OCR_MAX_VARIANTS` | `6` | Number of image preprocessing variants for local OCR. | Better local robustness, more CPU/time. | Faster local OCR, lower robustness. |
| `OCR_WARMUP` | `1` | Warm starts OCR engine on app startup. | N/A (`1` enabled). | `0` reduces startup work but first scan can be slower. |
| `OCR_DEBUG` | `0` | Adds debug metadata in OCR response. | `1` gives richer diagnostics. | `0` keeps payload leaner. |
| `OPENAI_MODEL` | `gpt-4.1-mini` | OpenAI model used for provider 1. | Larger model can improve extraction quality but cost/time may rise. | Smaller model can be faster/cheaper but less accurate. |
| `ANTHROPIC_MODEL` | `claude-3-5-sonnet-latest` | Anthropic model used for provider 2. | Stronger model can improve fallback quality but cost/time may rise. | Smaller model can be faster/cheaper but less accurate. |
| `CALIBRATION_FACTOR_MIN` | `0.1` | Lower bound for accepted weight calibration factor. | Accepts more aggressive down-scaling of K2 estimate. | Rejects low factors earlier. |
| `CALIBRATION_FACTOR_MAX` | `12.0` | Upper bound for accepted weight calibration factor. | Accepts stronger correction when K2 estimate is very low. | Rejects high factors earlier. |
| `REMAINING_WEIGHT_CHANGE_THRESHOLD_G` | `0.1` | Minimum delta before `remaining_weight` is written. | Reduces micro-flapping caused by noisy live values. | Applies even tiny changes, more jitter. |
| `CFS_REMAINLEN_MULTIPLIER` | `1.0` | Multiplier applied to raw `remainLen` before grams conversion. | Increases computed raw K2 grams if your firmware reports scaled length. | Decreases computed raw K2 grams. |

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
