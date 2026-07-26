# Catalogue Deployment

## Overview

The catalogue is deployed using Docker Compose.

`compose.yaml` and `.env` live in the repository root, one level above
this `catalogue/` folder. Run every `docker compose` command below from
the repository root.

---

# Services

## catalogue_mariadb

MariaDB database service.

Container:

```text
catalogue_mariadb
```

---

## catalogue_backend

FastAPI application.

Container:

```text
catalogue_backend
```

---

## catalogue_nginx

NGINX web server.

Container:

```text
catalogue_nginx
```

---

## adminer

Optional database administration interface.

Container:

```text
catalogue_adminer
```

Enabled using:

```bash
docker compose --profile dev up -d
```

---

# Starting the Application

```bash
docker compose up -d
```

---

# Stopping the Application

```bash
docker compose down
```

---

# Viewing Logs

All services:

```bash
docker compose logs
```

Backend only:

```bash
docker compose logs catalogue_backend
```

Database only:

```bash
docker compose logs catalogue_mariadb
```

---

# Updating the Application

Pull latest changes:

```bash
git pull
```

Restart containers:

```bash
docker compose down
docker compose up -d
```

Apply any new database migrations (safe to run every time - already-applied
migrations are skipped):

```bash
./catalogue/backend/migrations/run_migrations.sh
```

---

# Database Schema and Seed Data

First-time setup on a fresh, empty database:

```bash
./catalogue/backend/migrations/run_migrations.sh
```

This creates every table and view (`0000_initial_schema.sql`) and applies
all subsequent migrations in order - see `docs/database.md` for what each
table is for.

A fresh database has no users. To seed one example admin login and three
example teaching slides to log in with and look at:

```bash
docker exec -it catalogue_backend python3 /app/app/seed_example_data.py
```

Safe to re-run - skips anything that already exists.

## Migrating in a legacy archive

If you have an existing slide archive with a legacy metadata database to
migrate in (rather than starting from the example data above),
[dih-slide-reconciler](https://github.com/Jcarlosmiguel/dih-slide-reconciler)
crawls a real folder of slide files, reconciles it against a legacy
Slidepath DIH database, and emits a `.sql` file that imports directly into
this schema (`slides`/`slide_metadata`/`slide_technical_metadata`/
`slide_annotations`) - append-only, safe to run against a catalogue that
already has data in it. See that project's own README for usage and its
"Compatibility with slide-catalogue" section for the exact guarantees.

---

# Database Backup and Restore

Run from the repository root (where `compose.yaml`/`.env` live):

```bash
./backup_mariadb.sh
```

Creates a timestamped, permission-locked (`chmod 600`) dump under
`catalogue/backups/database/full/` - contains real user data including
password hashes, never committed to git.

```bash
./restore_mariadb.sh
```

Lists available backups, prompts you to pick one and confirm, then
restores it. Doesn't stop `catalogue_backend` first - do that yourself
if you want to guarantee no writes race the restore:

```bash
docker compose stop catalogue_backend
./restore_mariadb.sh
docker compose start catalogue_backend
```

# Thumbnail Backup and Restore

```bash
./backup_thumbnails.sh
```

Archives the whole `catalogue/thumbnails/` folder to a timestamped
`.tar.gz` under `catalogue/backups/thumbnails/`.

```bash
./restore_thumbnails.sh
```

Lists available thumbnail archives, prompts you to pick one and
confirm, then extracts it back into `catalogue/thumbnails/`, overwriting
what's there.

Neither of these covers per-file thumbnail replacement history during
normal manual-thumbnail maintenance - see
`docs/thumbnail-maintenance.md`'s own `thumbnail_backups/` mechanism for
that.

---

# Thumbnail Workflow

See:

```text
docs/thumbnail-maintenance.md
```

for complete thumbnail generation and maintenance procedures.

---

# Git Workflow

Check status:

```bash
git status
```

Commit changes:

```bash
git add .
git commit -m "Description"
```

Push changes:

```bash
git push
```

---

# Excluded Content

The following are intentionally excluded from Git:

```text
.env
backups/
thumbnails/
manual_thumbnails/
thumbnail_backups/
```

These contain generated content, backups or secrets.
