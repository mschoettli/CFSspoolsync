#!/usr/bin/env bash
# Manuelles Update â€” alternativ zu Watchtower.
# Pulls the latest Git version + images and restarts the stack.
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

echo "âœ… Update abgeschlossen"
docker compose ps

