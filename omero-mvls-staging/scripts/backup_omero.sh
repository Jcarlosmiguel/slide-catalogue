#!/bin/bash

set -euo pipefail

########################################
# --dry-run
########################################
# Prints exactly what would happen (target filename, DB version) without
# creating anything or touching the database. Read-only checks (Postgres
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
# Lives in ./scripts/ alongside backup_catalogue.sh etc. - one level
# below compose.yaml/.env, so this can't just `source .env` relative to
# wherever it happens to be invoked from (works if run as
# ./scripts/backup_omero.sh from the project root, breaks if invoked as
# `cd scripts && ./backup_omero.sh`). Always resolve to the parent of
# this script's own directory instead, regardless of the caller's cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

set -a
source .env
set +a

# Check Postgres is reachable. </dev/null for consistency with
# restore_omero.sh, even though this script has no later interactive
# prompts for stdin to clash with.
if ! docker compose exec -T "$POSTGRES_SERVICE" pg_isready -U "$OMEROPGUSER" >/dev/null 2>&1 </dev/null; then
    echo "ERROR: PostgreSQL is not running or not ready."
    exit 1
fi

if $DRY_RUN; then
    echo "DRY RUN: would create directory if missing: $BACKUP_DIR"
else
    mkdir -p "$BACKUP_DIR"
fi

# Get PostgreSQL version (e.g. 17.6)
PG_VERSION=$(
    docker compose exec -T "$POSTGRES_SERVICE" \
        psql -U "$OMEROPGUSER" -d "$OMEROPGDB" -tAc "SHOW server_version"
)

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="${BACKUP_DIR}/${OMEROPGDB}_pg${PG_VERSION}_${TIMESTAMP}.dump"

if $DRY_RUN; then
    echo "DRY RUN: would back up database '$OMEROPGDB' (PostgreSQL $PG_VERSION) to:"
    echo "  $BACKUP_FILE"
    echo "DRY RUN: no changes made."
    exit 0
fi

echo "Creating backup of database '$OMEROPGDB' (PostgreSQL $PG_VERSION)..."

docker compose exec -T "$POSTGRES_SERVICE" \
    pg_dump -U "$OMEROPGUSER" -Fc "$OMEROPGDB" > "$BACKUP_FILE"

if [ ! -s "$BACKUP_FILE" ]; then
    echo "ERROR: Backup failed (file is empty)."
    rm -f "$BACKUP_FILE"
    exit 1
fi

echo "Backup created: $BACKUP_FILE"
