# catalogue/

A searchable catalogue for virtual microscopy slide archives - search,
review, annotate, and export slides for teaching use.

For architecture, database schema, deployment mechanics, and
maintenance procedures, see `docs/` inside this folder
(`architecture.md`, `database.md`, `deployment.md`, `mariadb.md`,
`thumbnail-maintenance.md`) - this file only covers what's in each
top-level folder here.

## Source

| Folder | What's there |
|---|---|
| `backend/` | FastAPI application - auth, search, feedback, access requests, admin functions, system settings. `Dockerfile` builds the `catalogue_backend` container. |
| `frontend/` | Static HTML/CSS/JS served by `catalogue_nginx`. |
| `nginx/` | `catalogue.dev.conf` - `catalogue_nginx`'s own config (serves the frontend, `/thumbnails/`, `/documents/`, proxies `/api/` to the backend). |
| `tools/` | Maintenance scripts (thumbnail generation etc.) - see `docs/thumbnail-maintenance.md`. |
| `documents/` | User-facing documentation pages served by the app itself (About, Contact, workflow guides), not developer docs. |
| `docs/` | Developer/maintainer documentation for the catalogue app. |

## Generated / data (not tracked in git)

| Folder | What's there |
|---|---|
| `thumbnails/` | Generated slide thumbnails (`512/`, `1024/`, `2048/`), recreated from slide data. |
| `manual_thumbnails/` | Staging area for administrator-curated thumbnails. |
| `thumbnail_backups/` | Automatic backups made during thumbnail replacement. |
| `backups/` | MariaDB database dumps and archived per-table snapshots. Contains real user data including password hashes - never committed. |

## Getting started

See the top-level `README.md` and `compose.yaml` for how this app is built
and run, and `docs/deployment.md` for the full deployment walkthrough.
