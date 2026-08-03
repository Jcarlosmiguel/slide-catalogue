#!/bin/bash

set -euo pipefail

THUMBNAIL_DIR="./catalogue/thumbnails"
BACKUP_DIR="./catalogue/backups/thumbnails"

if [ ! -d "$THUMBNAIL_DIR" ] || [ -z "$(ls -A "$THUMBNAIL_DIR" 2>/dev/null)" ]; then
    echo "ERROR: $THUMBNAIL_DIR is missing or empty - nothing to back up."
    exit 1
fi

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="${BACKUP_DIR}/thumbnails_${TIMESTAMP}.tar.gz"

echo "Archiving $THUMBNAIL_DIR ..."

# -C so the archive contains 512/, 1024/, 2048/ at its root rather than
# the full ./catalogue/thumbnails/ path - restore_thumbnails.sh extracts
# it straight back into place with no path-stripping needed.
tar -czf "$BACKUP_FILE" -C "$THUMBNAIL_DIR" .

if [ ! -s "$BACKUP_FILE" ]; then
    echo "ERROR: Backup failed (file is empty)."
    rm -f "$BACKUP_FILE"
    exit 1
fi

echo "Backup created: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
