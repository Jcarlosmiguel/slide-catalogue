# Virtual Microscopy Catalogue

A self-hosted catalogue app for browsing, searching, and annotating virtual
microscopy slide archives - built for teaching use (search by organ/species/
stain, review slide metadata, flag corrections, export QuPath annotation
scripts, prepare slides for publication).

## Getting started

```bash
cp .env.example .env    # then fill in the required values, see below
docker compose up -d
```

The app will be available at `http://localhost:$HTTP_PORT` (see `.env`).

Required environment variables (see `compose.yaml` for the full list):

- `MARIADB_ROOT_PASSWORD`, `MARIADB_DATABASE`, `MARIADB_USER`, `MARIADB_PASSWORD`
- `APP_ENV`, `APP_SESSION_SECRET`, `APP_BASE_URL`
- `HTTP_PORT`, `ADMINER_PORT`
- `SHARE_ROOT_WINDOWS` / `SHARE_ROOT_MACOS` / `SHARE_ROOT_LINUX` - the mount
  paths of your slide archive share on each OS, shown to users as a
  ready-to-copy path
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` -
  outgoing mail for account activation/password reset

Run database migrations after first startup and after every pull (this also
creates the base schema automatically on a fresh, empty database):

```bash
./catalogue/backend/migrations/run_migrations.sh
```

On a fresh database there are no users yet. Seed one example admin login
and one example slide (with generated placeholder thumbnails) to have
something to log in with and look at:

```bash
docker exec -it catalogue_backend python3 /app/app/seed_example_data.py
```

Safe to re-run - it skips anything that already exists. Prints the example
login (`admin` / `ChangeMe123!`) - change that password before using this
anywhere beyond local testing.

## Where to look

| Folder | What's there |
|---|---|
| `catalogue/` | The application itself - see `catalogue/README.md`. |
| `compose.yaml` | Docker Compose stack (MariaDB, backend, nginx, optional mail relay and Adminer). |
| `backup_mariadb.sh` | Database backup script. |

For architecture, database schema, deployment, and maintenance docs, see
`catalogue/docs/`.
