#!/bin/bash

set -euo pipefail

set -a
source .env
set +a

BACKUP_DIR="./catalogue/backups/database/full"

# Check MariaDB is reachable. </dev/null matters here: without it,
# `docker compose exec -T` inherits this script's stdin, which would
# otherwise siphon input meant for the select/read prompts below.
if ! docker compose exec -T catalogue_mariadb healthcheck.sh --connect >/dev/null 2>&1 </dev/null; then
    echo "ERROR: MariaDB is not running or not ready."
    exit 1
fi

mapfile -t BACKUPS < <(find "$BACKUP_DIR" -maxdepth 1 -name "*.sql" 2>/dev/null | sort)

if [ ${#BACKUPS[@]} -eq 0 ]; then
    echo "No backups found in $BACKUP_DIR"
    exit 1
fi

select BACKUP_FILE in "${BACKUPS[@]}"; do
    [ -n "$BACKUP_FILE" ] && break
done

read -p "Restore database '$MARIADB_DATABASE' from $BACKUP_FILE? (y/N): " CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || exit 0

# A mariadb-dump --databases dump only contains CREATE DATABASE IF NOT
# EXISTS / CREATE TABLE (implicitly dropping+recreating each table it
# covers) plus data, so it replaces the tables it contains in place
# rather than the whole database - active connections aren't terminated
# and the database itself isn't dropped/recreated first. Stop
# catalogue_backend first if you want to guarantee no writes race the
# restore:
#   docker compose stop catalogue_backend
cat "$BACKUP_FILE" | docker compose exec -T catalogue_mariadb \
    mariadb -u root -p"$MARIADB_ROOT_PASSWORD"

echo "Restore completed. Restart catalogue_backend if you stopped it:"
echo "  docker compose start catalogue_backend"
