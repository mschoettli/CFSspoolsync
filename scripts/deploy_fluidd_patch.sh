#!/bin/sh
set -eu

# Deploy prebuilt Fluidd UI files (with CFS card) into /usr/share/fluidd.
# Supports source layouts:
# - /tmp/fluidd-new/*            (index.html + assets/)
# - /tmp/fluidd-new/dist/*       (nested dist directory)

SOURCE_ROOT="${1:-/tmp/fluidd-new}"
TARGET_ROOT="/usr/share/fluidd"
BACKUP_ROOT="/root/fluidd-backup-$(date +%Y%m%d-%H%M%S)"

if [ ! -d "$SOURCE_ROOT" ]; then
  echo "ERROR: Source directory not found: $SOURCE_ROOT" >&2
  exit 1
fi

if [ -f "$SOURCE_ROOT/index.html" ] && [ -d "$SOURCE_ROOT/assets" ]; then
  SOURCE_DIST="$SOURCE_ROOT"
elif [ -f "$SOURCE_ROOT/dist/index.html" ] && [ -d "$SOURCE_ROOT/dist/assets" ]; then
  SOURCE_DIST="$SOURCE_ROOT/dist"
else
  echo "ERROR: Could not find Fluidd build files in $SOURCE_ROOT" >&2
  echo "Expected index.html and assets/ (or dist/index.html and dist/assets/)." >&2
  exit 1
fi

echo "Creating backup at: $BACKUP_ROOT"
mkdir -p "$BACKUP_ROOT"
cp -a "$TARGET_ROOT"/. "$BACKUP_ROOT"/

echo "Deploying from: $SOURCE_DIST"
rm -rf "$TARGET_ROOT"/*
cp -a "$SOURCE_DIST"/. "$TARGET_ROOT"/

echo "Fixing ownership and permissions..."
chown -R root:root "$TARGET_ROOT"
find "$TARGET_ROOT" -type d -exec chmod 755 {} \;
find "$TARGET_ROOT" -type f -exec chmod 644 {} \;

echo "Reloading nginx..."
nginx -t
nginx -s reload

echo "Done."
echo "Validate with:"
echo "  curl -I http://127.0.0.1:4408/"
