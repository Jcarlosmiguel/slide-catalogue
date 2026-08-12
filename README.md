# Virtual Microscopy Catalogue

A self-hosted catalogue app for browsing, searching, and annotating virtual
microscopy slide archives - built for teaching use (search by organ/species/
stain, review slide metadata, flag corrections, export QuPath annotation
scripts, prepare slides for publication).

Not a replacement for [OMERO](https://www.openmicroscopy.org/omero/) -
a companion to it. This app indexes and curates the *entire* slide
archive directly from the raw files (thumbnails, search, metadata,
annotation - no OMERO import needed for any of that), while OMERO's own
storage-intensive pyramidal processing is reserved for whichever slides
are actually in active teaching use. See `catalogue/docs/architecture.md`
("Relationship to OMERO") for the full rationale.

Also supports DICOM slides (e.g. for a medical-school radiology
collection) alongside the usual whole-slide image formats - every DICOM
file is de-identified before being catalogued, never served raw. See
`catalogue/docs/dicom.md` for the two de-identification modes and where
each is applied.

## Getting started

```bash
cp .env.example .env    # then fill in the required values, see below
docker compose up -d
```

The app will be available at `http://localhost:$HTTP_PORT` (see `.env`).

Required environment variables (see `compose.yaml` for the full list):

- `MARIADB_ROOT_PASSWORD`, `MARIADB_DATABASE`, `MARIADB_USER`, `MARIADB_PASSWORD`
- `APP_ENV`, `APP_SESSION_SECRET`, `APP_BASE_URL`, `APP_ROOT_PATH`,
  `APP_COOKIE_SECURE` - set the last one `true` once served over HTTPS
- `HTTP_PORT`, `ADMINER_PORT`
- `SHARE_ROOT_WINDOWS` / `SHARE_ROOT_MACOS` / `SHARE_ROOT_LINUX` - the mount
  paths of your slide archive share on each OS, shown to users as a
  ready-to-copy path
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` -
  outgoing mail for account activation/password reset
- `MAIL_FROM_CONTACT`, `CONTACT_NOTIFICATION_EMAIL` - the public contact
  form's sender identity and where messages are actually delivered
  (server-side only, never shown to visitors)
- `INSTITUTION_ID_LABEL` - optional, what to call your institution's
  external identity number wherever the frontend displays it (e.g.
  "University ID", "Student/Staff Number") in place of the generic default

Run database migrations after first startup and after every pull (this also
creates the base schema automatically on a fresh, empty database):

```bash
./catalogue/backend/migrations/run_migrations.sh
```

On a fresh database there are no users yet. Seed one example admin login
and three example teaching slides (real histology images, non-human
specimens, with their thumbnails) to have something to log in with and
look at:

```bash
docker exec -it catalogue_backend python3 /app/app/seed_example_data.py
```

Safe to re-run - it skips anything that already exists. Prints the example
login (`admin` / `ChangeMe123!`) - change that password before using this
anywhere beyond local testing.

Separately, seed the Organ/Tissue/Species/Stain dictionaries with a real,
curated starting vocabulary (77 organs, 39 tissues, 50 species, 257
stains, 49 organ-tissue relationships) instead of leaving them empty -
worth running on a real deployment too, not just for local testing:

```bash
docker exec -it catalogue_backend python3 /app/app/seed_dictionaries.py
```

Also safe to re-run - skips anything that already exists by name.

## Where to look

| Folder | What's there |
|---|---|
| `catalogue/` | The application itself - see `catalogue/README.md`. |
| `compose.yaml` | Docker Compose stack (MariaDB, backend, nginx, optional mail relay and Adminer). |
| `backup_mariadb.sh` / `restore_mariadb.sh` | Database backup/restore scripts. |
| `backup_thumbnails.sh` / `restore_thumbnails.sh` | Thumbnail backup/restore scripts. |

For architecture, database schema, deployment, and maintenance docs, see
`catalogue/docs/` (`docs/deployment.md` covers all four backup/restore
scripts above).

## License

GNU Affero General Public License v3 (AGPL-3.0) - see [LICENSE](LICENSE).

## Copyright

Copyright (C) 2026 Joao Miguel.
