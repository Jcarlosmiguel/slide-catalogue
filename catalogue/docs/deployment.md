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

---

# Database Backup

Create a backup:

```bash
set -a
source .env
set +a

docker exec catalogue_mariadb mariadb-dump \
-u root \
-p"$MARIADB_ROOT_PASSWORD" \
"$MARIADB_DATABASE" \
> backup.sql
```

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
