#!/bin/bash

set -euo pipefail

THUMBNAIL_DIR="./catalogue/thumbnails"
BACKUP_DIR="./catalogue/backups/thumbnails"

mapfile -t BACKUPS < <(find "$BACKUP_DIR" -maxdepth 1 -name "*.tar.gz" 2>/dev/null | sort)

if [ ${#BACKUPS[@]} -eq 0 ]; then
    echo "No backups found in $BACKUP_DIR"
    exit 1
fi

select BACKUP_FILE in "${BACKUPS[@]}"; do
    [ -n "$BACKUP_FILE" ] && break
done

echo "This will overwrite the contents of $THUMBNAIL_DIR with $BACKUP_FILE."
read -p "Continue? (y/N): " CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || exit 0

mkdir -p "$THUMBNAIL_DIR"
tar -xzf "$BACKUP_FILE" -C "$THUMBNAIL_DIR"

echo "Restore completed into $THUMBNAIL_DIR."
