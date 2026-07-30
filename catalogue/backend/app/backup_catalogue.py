#!/usr/bin/env python3
"""Creates a new full database backup from inside the catalogue_backend
container - the docker-triggerable counterpart to
scripts/backup_catalogue.sh (host-only, runs via `docker compose exec`).

Only ever creates a new timestamped file under /srv/backups - never reads,
lists, or deletes existing backups, so the volume mount backing that path
only needs to support new files being written, never modified or removed by
this code path. There is deliberately no restore equivalent here: restore
stays command-line only (scripts/restore_catalogue.sh on the host), never
docker- or webpage-triggered.

Reuses the same DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME env vars the
rest of the backend already connects with - confirmed against a throwaway
MariaDB container that the app user the official image auto-provisions
(GRANT ALL PRIVILEGES on just that one database) already has everything
--single-transaction --routines --triggers needs, so no extra grants or a
separate root/backup-only credential are required.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

BACKUP_DIR = Path("/srv/backups")


def _run(args, password, **kwargs):
    # MYSQL_PWD instead of -p<password> keeps the password out of the
    # process list (`ps aux` inside the container), unlike the host script's
    # -p"$MARIADB_ROOT_PASSWORD" - a low-cost improvement, not a functional
    # requirement.
    env = {**os.environ, "MYSQL_PWD": password}
    return subprocess.run(args, env=env, **kwargs)


def _mariadb_version(host, port, user, password):
    result = _run(
        ["mariadb", "-h", host, "-P", str(port), "-u", user, "-sNe", "SELECT VERSION();"],
        password,
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def create_backup():
    host = os.environ["DB_HOST"]
    port = os.environ.get("DB_PORT", "3306")
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    database = os.environ["DB_NAME"]

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    version = _mariadb_version(host, port, user, password)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = BACKUP_DIR / f"{database}_mariadb{version}_{timestamp}.sql"

    with open(backup_file, "wb") as fh:
        # --databases (rather than a trailing db name) embeds CREATE DATABASE
        # IF NOT EXISTS / USE statements, matching backup_catalogue.sh so
        # dumps from either path replay the same way with restore_catalogue.sh.
        proc = _run(
            ["mariadb-dump", "-h", host, "-P", str(port), "-u", user,
             "--single-transaction", "--routines", "--triggers",
             "--databases", database],
            password,
            stdout=fh, stderr=subprocess.PIPE,
        )

    if proc.returncode != 0 or backup_file.stat().st_size == 0:
        stderr = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
        backup_file.unlink(missing_ok=True)
        raise RuntimeError(f"mariadb-dump failed: {stderr.strip() or 'empty output'}")

    # The dump contains real user data including password hashes (see the
    # users table in catalogue/docs/database.md).
    os.chmod(backup_file, 0o600)

    return backup_file


def main():
    backup_file = create_backup()
    print(f"Backup created: {backup_file}")


if __name__ == "__main__":
    main()
