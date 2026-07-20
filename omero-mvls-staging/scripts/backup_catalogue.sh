#!/bin/bash

set -euo pipefail

########################################
# --dry-run
########################################
# Prints exactly what would happen (target filename, DB version) without
# creating anything or touching the database. Read-only checks (MariaDB
# reachability, version query) still run for real, since an accurate
# preview needs them.
DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        *) echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done

########################################
# Locate the compose project root
########################################
# Lives in ./scripts/ alongside backup_omero.sh etc. - one level below
# compose.yaml/.env, so this can't just `source .env` relative to
# wherever it happens to be invoked from (works if run as
# ./scripts/backup_catalogue.sh from the project root, breaks if
# invoked as `cd scripts && ./backup_catalogue.sh`). Always resolve to
# the parent of this script's own directory instead, regardless of the
# caller's cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

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

if $DRY_RUN; then
    echo "DRY RUN: would create directory if missing: $BACKUP_DIR"
else
    mkdir -p "$BACKUP_DIR"
fi

# Get MariaDB version (e.g. 11.4.2-MariaDB)
MARIADB_VERSION=$(
    docker compose exec -T catalogue_mariadb \
        mariadb -u root -p"$MARIADB_ROOT_PASSWORD" -sNe "SELECT VERSION();" 2>/dev/null | tr -d '\r\n'
)

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="${BACKUP_DIR}/${MARIADB_DATABASE}_mariadb${MARIADB_VERSION}_${TIMESTAMP}.sql"

if $DRY_RUN; then
    echo "DRY RUN: would back up database '$MARIADB_DATABASE' (MariaDB $MARIADB_VERSION) to:"
    echo "  $BACKUP_FILE"
    echo "DRY RUN: no changes made."
    exit 0
fi

echo "Creating backup of database '$MARIADB_DATABASE' (MariaDB $MARIADB_VERSION)..."

# --databases (rather than just naming the db as a trailing arg) embeds
# CREATE DATABASE IF NOT EXISTS / USE statements in the dump, so
# restore_catalogue.sh can replay it without needing the database to
# already exist. --single-transaction takes a consistent InnoDB snapshot
# without locking tables; --routines/--triggers include stored
# procedures/triggers, which a plain mariadb-dump would otherwise skip.
docker compose exec -T catalogue_mariadb \
    mariadb-dump -u root -p"$MARIADB_ROOT_PASSWORD" \
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
