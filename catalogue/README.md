# catalogue/

The MVLS Virtual Microscopy Catalogue app, merged into the omero-mvls
compose stack (see the root `README.md` and `docs/merge-history.md` one
level up for how it fits in and how it got there). This folder is the
whole app payload, transferred as a unit rather than tracked directly
in omero-mvls's own git history - see the root `docs/` folder's
`.gitignore` options for the tracking strategies available.

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
| `nginx/` | `catalogue.dev.conf` - `catalogue_nginx`'s own config (serves the frontend, `/thumbnails/`, `/documents/`, proxies `/api/` to the backend). Separate from the shared omero-mvls `nginx/nginx.conf` one level up, which only routes by domain into this. |
| `tools/` | Maintenance scripts (thumbnail generation etc.) - see `docs/thumbnail-maintenance.md`. |
| `documents/` | User-facing documentation pages served by the app itself (About, Contact, workflow guides), not developer docs. |
| `docs/` | Developer/maintainer documentation for the catalogue app specifically. |

## Generated / data (not tracked in git, regardless of strategy)

| Folder | What's there |
|---|---|
| `thumbnails/` | Generated slide thumbnails (`512/`, `1024/`, `2048/`), recreated from slide data. |
| `manual_thumbnails/` | Staging area for administrator-curated thumbnails. |
| `thumbnail_backups/` | Automatic backups made during thumbnail replacement. |
| `backups/` | MariaDB database dumps (`backup_catalogue.sh`'s output lands in `backups/database/full/`) and archived per-table snapshots (`backups/database/archive-tables/`). Contains real user data including password hashes - never committed. |

## Root-level files

`dotenv` - catalogue's own env var reference from when it ran as a
standalone deployment; the merged deployment's real variables live in
the root `.env` one level up instead (built from `docs/dotenv` there).
`mvls-catalogue_tree.txt` - a generated directory listing, not
hand-maintained.
