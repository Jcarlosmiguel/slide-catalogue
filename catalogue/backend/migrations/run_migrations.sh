#!/bin/bash
# Applies any pending 000N_*.sql files in this directory against
# the catalogue database, tracking what's already run in a schema_migrations
# table - always safe to re-run, only genuinely new migrations get applied.
#
# Usage:
#   ./run_migrations.sh              # apply all pending migrations
#   ./run_migrations.sh --dry-run    # show what would run, don't apply anything
#
# By default connects through the catalogue_mariadb docker container
# (matching this project's compose setup) and reads the DB password from
# ../../../.env (MARIADB_PASSWORD=...). To connect directly instead (e.g. a
# server where mariadb isn't containerized the same way), set MARIADB_HOST.
#
# Env vars (all optional):
#   MARIADB_CONTAINER   default: catalogue_mariadb
#   MARIADB_USER        default: catalogue_app
#   MARIADB_PASSWORD    default: read from ../../../.env
#   MARIADB_DATABASE    default: catalogue
#   MARIADB_HOST        if set, connects directly via the mariadb CLI instead
#                        of docker exec
#   MARIADB_PORT        default: 3306 (only used with MARIADB_HOST)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

CONTAINER="${MARIADB_CONTAINER:-catalogue_mariadb}"
DB_USER="${MARIADB_USER:-catalogue_app}"
DB_NAME="${MARIADB_DATABASE:-catalogue}"
DB_PASSWORD="${MARIADB_PASSWORD:-}"

if [[ -z "$DB_PASSWORD" ]]; then
  ENV_FILE="$SCRIPT_DIR/../../../.env"
  if [[ -f "$ENV_FILE" ]]; then
    DB_PASSWORD="$(grep -E '^MARIADB_PASSWORD=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
  fi
fi

if [[ -z "$DB_PASSWORD" ]]; then
  echo "Error: no DB password found. Set MARIADB_PASSWORD, or ensure .env has MARIADB_PASSWORD=..." >&2
  exit 1
fi

run_sql() {
  if [[ -n "${MARIADB_HOST:-}" ]]; then
    MYSQL_PWD="$DB_PASSWORD" mariadb -h "$MARIADB_HOST" -P "${MARIADB_PORT:-3306}" -u "$DB_USER" "$@" "$DB_NAME"
  else
    # MYSQL_PWD instead of -p<password> keeps mariadb's own argv (visible
    # via `ps` to anyone else inside the container) clean, matching
    # backup_catalogue.py's own reasoning for the same thing. Note this
    # doesn't hide it from `ps` on the *host* - the expanded value is
    # still part of this docker exec invocation's own argv there either
    # way; a full fix would need a temp --defaults-extra-file instead.
    docker exec -i -e MYSQL_PWD="$DB_PASSWORD" "$CONTAINER" mariadb -u "$DB_USER" "$@" "$DB_NAME"
  fi
}

echo "CREATE TABLE IF NOT EXISTS schema_migrations (
  filename VARCHAR(255) PRIMARY KEY COMMENT 'Migration filename, e.g. 0001_reviewer_expert_roles.sql.',
  applied_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'When this migration was applied.'
) COMMENT='Tracks which migrations/*.sql files have already been applied, so run_migrations.sh only ever applies each one once.';" | run_sql

mapfile -t applied < <(echo "SELECT filename FROM schema_migrations;" | run_sql -N)

pending=()
for f in "$SCRIPT_DIR"/[0-9][0-9][0-9][0-9]_*.sql; do
  [[ -e "$f" ]] || continue
  base="$(basename "$f")"
  is_applied=false
  for a in "${applied[@]:-}"; do
    [[ "$a" == "$base" ]] && is_applied=true && break
  done
  $is_applied || pending+=("$base")
done

if [[ ${#pending[@]} -eq 0 ]]; then
  echo "No pending migrations - up to date."
  exit 0
fi

echo "Pending migrations:"
printf '  %s\n' "${pending[@]}"

if $DRY_RUN; then
  echo "(dry run - nothing applied)"
  exit 0
fi

for base in "${pending[@]}"; do
  echo "Applying $base ..."
  run_sql < "$SCRIPT_DIR/$base"
  echo "INSERT INTO schema_migrations (filename) VALUES ('$base');" | run_sql
  echo "  done."
done

echo "All migrations applied."
