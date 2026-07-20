#!/bin/bash

set -euo pipefail

########################################
# --dry-run
########################################
# Shows which backup would be selected, runs the major-version check
# below for real (it's read-only), but stops before touching the
# database - no pg_terminate_backend, no pg_restore.
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
# Lives in ./scripts/ alongside restore_catalogue.sh etc. - one level
# below compose.yaml/.env, so this can't just `source .env` relative to
# wherever it happens to be invoked from (works if run as
# ./scripts/restore_omero.sh from the project root, breaks if invoked
# as `cd scripts && ./restore_omero.sh`). Always resolve to the parent
# of this script's own directory instead, regardless of the caller's
# cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

set -a
source .env
set +a

# Check Postgres is reachable. </dev/null matters here: without it,
# `docker compose exec -T` inherits this script's stdin, which would
# otherwise siphon input meant for the select/read prompts below (same
# issue found and fixed in restore_catalogue.sh).
if ! docker compose exec -T "$POSTGRES_SERVICE" pg_isready -U "$OMEROPGUSER" >/dev/null 2>&1 </dev/null; then
    echo "ERROR: PostgreSQL is not running or not ready."
    exit 1
fi

mapfile -t BACKUPS < <(find "$BACKUP_DIR" -maxdepth 1 -name "*.dump" | sort)

if [ ${#BACKUPS[@]} -eq 0 ]; then
    echo "No backups found"
    exit 1
fi

select BACKUP_FILE in "${BACKUPS[@]}"; do
    [ -n "$BACKUP_FILE" ] && break
done

########################################
# Major-version mismatch check
########################################
# PostgreSQL major-version upgrades are NOT just "restore the old dump
# into the new server" - see the project README's original warning, and
# https://www.postgresql.org/docs/current/upgrading.html. A dump/restore
# across major versions can fail outright, or in some cases "succeed"
# while leaving data in a state that doesn't match what the source
# database actually had - don't rely on it as an upgrade path on its
# own. The safe procedure:
#   1. Temporarily run a PostgreSQL container matching the DUMP's major
#      version, and restore this backup into it there.
#   2. From that instance, take a fresh pg_dump export.
#   3. Restore THAT export into the current (different-major-version)
#      server instead of this original file directly.
#
# Detection here is best-effort (parses version strings out of
# pg_restore's header and the live server) - if either can't be parsed,
# this check is silently skipped rather than blocking a legitimate
# same-version restore.
RUNNING_VERSION=$(
    docker compose exec -T "$POSTGRES_SERVICE" \
        psql -U "$OMEROPGUSER" -d "$OMEROPGDB" -tAc "SHOW server_version" 2>/dev/null </dev/null || true
)
RUNNING_MAJOR=$(echo "$RUNNING_VERSION" | sed -E 's/^([0-9]+).*/\1/')

DUMP_VERSION_LINE=$(
    docker compose exec -T "$POSTGRES_SERVICE" pg_restore -l < "$BACKUP_FILE" 2>/dev/null \
        | grep "Dumped from database version" || true
)
DUMP_MAJOR=$(echo "$DUMP_VERSION_LINE" | sed -E 's/.*version: ([0-9]+).*/\1/')

if [[ "$RUNNING_MAJOR" =~ ^[0-9]+$ ]] && [[ "$DUMP_MAJOR" =~ ^[0-9]+$ ]] && [ "$RUNNING_MAJOR" != "$DUMP_MAJOR" ]; then
    echo
    echo "############################################################"
    echo "# WARNING: cross-major-version restore detected"
    echo "############################################################"
    echo "This backup was taken from PostgreSQL $DUMP_MAJOR ($(echo "$DUMP_VERSION_LINE" | sed -E 's/.*version: //'))."
    echo "The currently running server is PostgreSQL $RUNNING_MAJOR ($RUNNING_VERSION)."
    echo
    echo "Restoring this file directly into a different major version is"
    echo "not a supported upgrade path on its own - see:"
    echo "  https://www.postgresql.org/docs/current/upgrading.html"
    echo
    echo "Safe procedure instead:"
    echo "  1. Temporarily run a PostgreSQL $DUMP_MAJOR container and restore"
    echo "     this backup into it there."
    echo "  2. From that PostgreSQL $DUMP_MAJOR instance, take a fresh pg_dump"
    echo "     export."
    echo "  3. Restore THAT export into this PostgreSQL $RUNNING_MAJOR server"
    echo "     instead of this original file directly."
    echo "############################################################"
    echo

    if $DRY_RUN; then
        echo "DRY RUN: would stop here and require explicit confirmation to proceed."
        exit 0
    fi

    read -p "Type UPGRADE to restore this file directly anyway, or press Enter to abort: " CONFIRM_UPGRADE
    if [ "$CONFIRM_UPGRADE" != "UPGRADE" ]; then
        echo "Aborted."
        exit 0
    fi
fi

if $DRY_RUN; then
    echo "DRY RUN: would restore database '$OMEROPGDB' from:"
    echo "  $BACKUP_FILE"
    echo "DRY RUN: would terminate active connections to '$OMEROPGDB', then run pg_restore --clean --create --if-exists."
    echo "DRY RUN: no changes made."
    exit 0
fi

read -p "Restore database '$OMEROPGDB'? (y/N): " CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || exit 0

docker compose exec -T "$POSTGRES_SERVICE" psql \
    -U "$OMEROPGUSER" \
    -d postgres \
    -c "SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname='$OMEROPGDB'
          AND pid <> pg_backend_pid();"

cat "$BACKUP_FILE" | docker compose exec -T "$POSTGRES_SERVICE" \
    pg_restore -v \
    --clean \
    --create \
    --if-exists \
    -U "$OMEROPGUSER" \
    -d postgres

echo "Restore completed. Please restart docker compose."
