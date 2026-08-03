#!/bin/bash

set -euo pipefail

set -a
source .env
set +a

BACKUP_DIR="./catalogue/backups/database/full"

# Check MariaDB is reachable. </dev/null matters here: without it,
# `docker compose exec -T` inherits this script's stdin, and if this
# script is ever run non-interactively with input piped in, that input
# can get siphoned here instead of reaching later prompts.
if ! docker compose exec -T catalogue_mariadb healthcheck.sh --connect >/dev/null 2>&1 </dev/null; then
    echo "ERROR: MariaDB is not running or not ready."
    exit 1
fi

mkdir -p "$BACKUP_DIR"

# Get MariaDB version (e.g. 11.4.2-MariaDB)
# MYSQL_PWD instead of -p<password> keeps mariadb's own argv (visible via
# `ps` to anyone else on the host or inside the container) clean.
MARIADB_VERSION=$(
    docker compose exec -T -e MYSQL_PWD="$MARIADB_ROOT_PASSWORD" catalogue_mariadb \
        mariadb -u root -sNe "SELECT VERSION();" 2>/dev/null | tr -d '\r\n'
)

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="${BACKUP_DIR}/${MARIADB_DATABASE}_mariadb${MARIADB_VERSION}_${TIMESTAMP}.sql"

echo "Creating backup of database '$MARIADB_DATABASE' (MariaDB $MARIADB_VERSION)..."

# --databases (rather than just naming the db as a trailing arg) embeds
# CREATE DATABASE IF NOT EXISTS / USE statements in the dump, so
# restore_mariadb.sh can replay it without needing the database to
# already exist. --single-transaction takes a consistent InnoDB snapshot
# without locking tables; --routines/--triggers include stored
# procedures/triggers, which a plain mariadb-dump would otherwise skip.
docker compose exec -T -e MYSQL_PWD="$MARIADB_ROOT_PASSWORD" catalogue_mariadb \
    mariadb-dump -u root \
    --single-transaction --routines --triggers --databases \
    "$MARIADB_DATABASE" > "$BACKUP_FILE"

if [ ! -s "$BACKUP_FILE" ]; then
    echo "ERROR: Backup failed (file is empty)."
    rm -f "$BACKUP_FILE"
    exit 1
fi

# This dump contains real user data including password hashes (see the
# `users` table in catalogue/docs/database.md) - don't leave it at
# whatever the ambient umask happens to allow.
chmod 600 "$BACKUP_FILE"

echo "Backup created: $BACKUP_FILE"
