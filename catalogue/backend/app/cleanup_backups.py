"""Deletes old full-database backups under /srv/backups, keeping only the
most recent N.

The only place backups are ever listed or deleted from - deliberately
absent until now (see backup_catalogue.py's own docstring: "never reads,
lists, or deletes existing backups"). The user explicitly revisited that
decision this session to add cleanup specifically, given how many
timestamped backups accumulate; restore and browsing/download stay
off-limits, unchanged.

Only ever touches files matching the exact naming convention
backup_catalogue.py itself writes ("{DB_NAME}_mariadb<version>_<timestamp>.sql")
- confirmed against the real directory that other, unrelated .sql files
(one-off import dumps transferred through this same folder, an old
generically-named mariadb.sql) also live there and must never be touched.
"""

import os
from pathlib import Path

BACKUP_DIR = Path("/srv/backups")


def _real_backups():
    """Every file matching this deployment's own backup naming pattern,
    oldest first - the timestamp is embedded in the filename
    (YYYY-MM-DD_HH-MM-SS), so a plain name sort is already chronological."""
    pattern = f"{os.environ['DB_NAME']}_mariadb*.sql"
    return sorted(
        (f for f in BACKUP_DIR.glob(pattern) if f.is_file()),
        key=lambda f: f.name,
    )


def cleanup(keep=3, dry_run=True):
    """Deletes every backup except the most recent `keep`. dry_run=True
    (the default) only reports what would happen - the caller must pass
    dry_run=False explicitly to actually delete anything."""

    if keep < 1:
        raise ValueError("keep must be at least 1")

    backups = _real_backups()
    to_keep = backups[-keep:]
    to_delete = backups[:-keep] if len(backups) > keep else []

    deleted = []
    for f in to_delete:
        size_bytes = f.stat().st_size
        if not dry_run:
            f.unlink()
        deleted.append({"filename": f.name, "size_bytes": size_bytes})

    return {
        "dry_run": dry_run,
        "kept": [f.name for f in to_keep],
        "deleted": deleted,
    }
