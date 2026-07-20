#!/bin/bash

set -euo pipefail

########################################
# --dry-run
########################################
# Shows which backup would be selected, but stops before touching the
# database.
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
# Lives in ./scripts/ alongside restore_omero.sh etc. - one level below
# compose.yaml/.env, so this can't just `source .env` relative to
# wherever it happens to be invoked from (works if run as
# ./scripts/restore_catalogue.sh from the project root, breaks if
# invoked as `cd scripts && ./restore_catalogue.sh`). Always resolve to
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
# `docker compose exec -T` inherits this script's stdin, which would
# otherwise siphon input meant for the select/read prompts below.
if ! docker compose exec -T catalogue_mariadb healthcheck.sh --connect >/dev/null 2>&1 </dev/null; then
    echo "ERROR: MariaDB is not running or not ready."
    exit 1
fi

mapfile -t BACKUPS < <(find "$BACKUP_DIR" -maxdepth 1 -name "*.sql" | sort)

if [ ${#BACKUPS[@]} -eq 0 ]; then
    echo "No backups found"
    exit 1
fi

select BACKUP_FILE in "${BACKUPS[@]}"; do
    [ -n "$BACKUP_FILE" ] && break
done

if $DRY_RUN; then
    echo "DRY RUN: would restore database '$MARIADB_DATABASE' from:"
    echo "  $BACKUP_FILE"
    echo "DRY RUN: no changes made."
    exit 0
fi

read -p "Restore database '$MARIADB_DATABASE' from $BACKUP_FILE? (y/N): " CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || exit 0

# Unlike restore_omero.sh (Postgres), this doesn't terminate active
# connections or drop/recreate the database first - a mariadb-dump
# --databases dump only contains CREATE DATABASE IF NOT EXISTS / CREATE
# TABLE (implicitly dropping+recreating each table it covers) plus data,
# so it replaces the tables it contains in place rather than the whole
# database. Stop catalogue_backend first if you want to guarantee no
# writes race the restore:
#   docker compose stop catalogue_backend
cat "$BACKUP_FILE" | docker compose exec -T catalogue_mariadb \
    mariadb -u root -p"$MARIADB_ROOT_PASSWORD"

echo "Restore completed. Restart catalogue_backend if you stopped it:"
echo "  docker compose start catalogue_backend"
