#!/usr/bin/env bash
# Manuelles Update — alternativ zu Watchtower.
# Zieht neueste Git-Version + Images und startet den Stack neu.
set -euo pipefail

cd "$(dirname "$0")"

echo "==> git pull"
git pull --ff-only

echo "==> pulling images"
docker compose pull

echo "==> restarting services"
docker compose up -d

echo "==> cleanup"
docker image prune -f

echo "✅ Update abgeschlossen"
docker compose ps
