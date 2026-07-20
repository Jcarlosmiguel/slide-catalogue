#!/bin/bash

set -uo pipefail
# Deliberately NOT set -e at this level: a failure in one backup should
# not prevent the other from being attempted. Each sub-script has its
# own set -euo pipefail internally and fails loudly on its own.

########################################
# Require root
########################################
# Runs backup_omero.sh (Postgres/OMERO) and backup_catalogue.sh
# (MariaDB/Catalogue) back to back. Requires sudo for consistent,
# predictable file ownership on the backups it produces, regardless of
# whether it's run interactively or from a root cron job - same
# reasoning as certificates.sh's guard.
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: this script must be run with sudo."
    exit 1
fi

########################################
# --dry-run
########################################
# Passed straight through to both sub-scripts.
DRY_RUN_ARGS=()
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN_ARGS=(--dry-run) ;;
        *) echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done

########################################
# Always run from this script's own directory (./scripts/, alongside
# its sibling scripts), so it works the same whether invoked as
# ./backup_all.sh, via an absolute path, or from cron. It doesn't need
# to locate compose.yaml/.env itself - backup_omero.sh and
# backup_catalogue.sh each do that on their own regardless of cwd, this
# just needs to find its two siblings.
########################################
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "########################################################"
if [ ${#DRY_RUN_ARGS[@]} -gt 0 ]; then
    echo "# Combined backup DRY RUN started: $START_TIME"
else
    echo "# Combined backup started: $START_TIME"
fi
echo "# Running from: $SCRIPT_DIR"
echo "########################################################"

OMERO_STATUS="FAILED"
CATALOGUE_STATUS="FAILED"

echo
echo "=== [1/2] OMERO Postgres backup (backup_omero.sh) ==="
if ./backup_omero.sh "${DRY_RUN_ARGS[@]}"; then
    OMERO_STATUS="OK"
else
    echo "OMERO Postgres backup FAILED (exit code $?) - see output above."
fi

echo
echo "=== [2/2] Catalogue MariaDB backup (backup_catalogue.sh) ==="
if ./backup_catalogue.sh "${DRY_RUN_ARGS[@]}"; then
    CATALOGUE_STATUS="OK"
else
    echo "Catalogue MariaDB backup FAILED (exit code $?) - see output above."
fi

END_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo
echo "########################################################"
echo "# Combined backup finished: $END_TIME"
echo "########################################################"
echo "OMERO Postgres backup    : $OMERO_STATUS"
echo "Catalogue MariaDB backup : $CATALOGUE_STATUS"

if [ "$OMERO_STATUS" = "OK" ] && [ "$CATALOGUE_STATUS" = "OK" ]; then
    if [ ${#DRY_RUN_ARGS[@]} -gt 0 ]; then
        echo "Result: dry run completed, no changes made."
    else
        echo "Result: both backups completed successfully."
    fi
    exit 0
else
    echo "Result: at least one backup FAILED - check the output above."
    exit 1
fi
