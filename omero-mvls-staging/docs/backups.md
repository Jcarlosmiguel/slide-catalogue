# Backups and restores

Five scripts in `scripts/`, deliberately kept as separate single-purpose
tools rather than one script with flags:

| Script | Does |
|---|---|
| `backup_omero.sh` | Backs up the OMERO Postgres database (`pg_dump`, custom format) to `./backups/`. |
| `restore_omero.sh` | Interactive - picks a file from `./backups/`, restores it. See "Postgres major-version restores" below before using this one. |
| `backup_catalogue.sh` | Backs up the Catalogue MariaDB database (`mariadb-dump --databases`, so the dump can recreate the database from nothing) to `catalogue/backups/database/full/`. |
| `restore_catalogue.sh` | Interactive - picks a file from that same folder, restores it. |
| `backup_all.sh` | Runs `backup_omero.sh` then `backup_catalogue.sh` back to back. Requires `sudo` (consistent file ownership regardless of who/what runs it - manual invocation or a root cron job). One failing doesn't stop the other from being attempted; exits non-zero if either failed, for cron/monitoring. |

**No `restore_all.sh`.** Backing up both databases together is a
reasonable routine action; restoring both together isn't something to
do casually - keeping them separate means a restore is always a
deliberate, single-database decision.

Postgres and MariaDB backup/restore stay in separate scripts rather
than one combined tool because Postgres has real major-version
migration constraints MariaDB doesn't share - see below.

## `--dry-run`

All five accept it. Prints exactly what would happen (target filename,
database version, which backup file would be selected) without
creating anything or touching the database. Read-only checks
(reachability, version queries) still run for real, since an accurate
preview needs them. `backup_all.sh --dry-run` passes the flag through
to both sub-scripts.

```bash
scripts/backup_omero.sh --dry-run
scripts/restore_omero.sh --dry-run
scripts/backup_catalogue.sh --dry-run
scripts/restore_catalogue.sh --dry-run
scripts/backup_all.sh --dry-run
```

Tested against real throwaway Postgres/MariaDB containers - confirmed
zero files created and zero database state changes for every script,
including from both possible invocation styles (`scripts/x.sh` from the
project root, and `cd scripts && ./x.sh`).

## Postgres major-version restores - read before you need it

Restoring a Postgres dump into a server running a **different major
version** (e.g. a backup taken under Postgres 15, restored into a
Postgres 16 container) is not a supported upgrade path on its own - see
[the official PostgreSQL upgrade docs](https://www.postgresql.org/docs/current/upgrading.html).
`pg_restore` can fail outright, or in some cases "succeed" while leaving
data in a state that doesn't actually match the source database.

**`restore_omero.sh` detects this automatically.** After you pick a
backup file, it compares the Postgres major version embedded in that
dump (read via `pg_restore -l`) against the version the currently
running server reports (`SHOW server_version`). If they differ, it
prints a warning explaining the mismatch and the safe procedure below,
and - instead of the normal `y`/`N` prompt - requires typing the literal
word `UPGRADE` to proceed. Pressing Enter (or anything else) aborts
cleanly with no changes made. Verified against a real cross-version case
(a genuine Postgres 15 dump, restored against a running Postgres 16
server) - correctly warned and blocked until explicitly overridden.

The safe procedure it describes:

1. Temporarily run a Postgres container matching the **dump's** major version, and restore the backup into it there.
2. From that instance, take a fresh `pg_dump` export.
3. Restore *that* export into the currently running (different-major-version) server - not the original file directly.

Detection is best-effort - if either version string can't be parsed
(unusual dump format, unexpected `psql` output), the check is silently
skipped rather than blocking a legitimate same-version restore. If
you're ever unsure, the safest move is always the 3-step procedure
above regardless of what the script does or doesn't warn about.

## A stdin gotcha already fixed here

`docker compose exec -T` inherits the invoking script's stdin. Without
an explicit `</dev/null` on read-only checks that run before an
interactive `select`/`read` prompt, piped/scripted input meant for that
later prompt can get silently consumed early, causing the prompt to
fail with an "unbound variable" error. Found in both
`restore_catalogue.sh` and (originally) `restore_database.sh`'s own
Postgres readiness check while testing non-interactively - fixed in
both; never an issue when a human types answers live at a terminal,
only under automation/scripted testing.
