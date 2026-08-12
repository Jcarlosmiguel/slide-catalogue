# catalogue/tools/

Standalone scripts for maintaining the catalogue database/thumbnails
outside the web app. Full workflow explanations live in
`../docs/thumbnail-maintenance.md` - this is just a quick reference for
what's here.

Plain Python scripts, not `docker compose exec` wrappers - most need to
be run with `python3` either on a host with direct filesystem access to
the slide archive (thumbnail generation) or with `--db-*` flags pointing
at the target MariaDB. Check each script's own `--help`/header docstring
for exact invocation.

| Script | Purpose | Docs |
|---|---|---|
| `generate_2048_png_thumbnails.py` | Generates a cropped 2048px PNG thumbnail directly from a slide file (OpenSlide-first, TiffSlide-fallback). Paired with `sync_manual_thumbnails.py` for *replacing* an existing thumbnail - backs the old one up before writing the new one. | `../docs/thumbnail-maintenance.md` |
| `populate_new_slide_thumbnails.py` | Generates thumbnails for every slide in the database that doesn't have one yet (e.g. after a fresh import batch) - same OpenSlide/TiffSlide approach, safe to re-run. Slides where automated generation fails (multi-scene/multiview files) are written to a report for manual follow-up instead of silently skipped. DICOM slides use a separate pydicom-based generator and are skipped entirely (never read at all) if not yet de-identified - see `../docs/dicom.md`. | `../docs/thumbnail-maintenance.md`, `../docs/dicom.md` |
| `export_annotations_ome_xml.py` | Generates one OME-XML file per slide with stored annotations, straight from the database - no QuPath round-trip. Offline/archival equivalent of the "Download annotations (OME-XML)" button on a slide's own page. | Own header docstring; user-facing equivalent documented in `../frontend/documents/script_annotation.html` |
| `find_cmp_candidates.py` | Read-only: scans filenames for the lettering/numbering conventions real curated comparison (CMP) slides use, reports ones not yet flagged in `stain_dictionary`. A starting point for a human to review, not a detector - real CMP slides can exist with no filename marker at all. | `../docs/database.md` (`stain_dictionary` section) |

## Related, not in this directory

- `../backend/app/sync_manual_thumbnails.py` - the second half of the
  manual thumbnail workflow (picks up PNGs dropped in
  `manual_thumbnails/`). Runs *inside* the `catalogue_backend` container,
  not from here directly - see `../docs/thumbnail-maintenance.md`.
- `../backend/app/backup_catalogue.py` - triggered via the admin-only
  `POST /api/admin/backup` endpoint, not run standalone.
- `../backend/app/sync_cmp_flags.py` - the sysadmin Maintenance Jobs
  page's "Sync comparison flags" button and the live per-correction
  check both call this directly; no standalone CLI usage.
- `../backend/app/cleanup_backups.py` - triggered via the sysadmin
  Maintenance Jobs page only, not run standalone.
- `../backend/app/resend_pending_activations.py` - resends the activation
  invite email for any `PENDING_ACTIVATION` account whose original email
  silently failed (e.g. during an SMTP outage) - regenerates the token
  first if it's since expired. Run *inside* `catalogue_backend`
  (`docker compose exec catalogue_backend python3 -m app.resend_pending_activations`
  - must be `-m`, not a file path, so the `app.main` import resolves).
  `--execute` to actually send (default is a dry run); `--user-id` to
  target one account.
- `../backend/app/resend_pending_password_resets.py` - same idea for a
  single user's most recent password-reset email, for when someone
  reports not receiving one. Unlike the activation script, this is never
  a bulk sweep - a password reset is a per-request event (old, unused,
  expired requests are completely normal, not something to resend) so
  `--execute` always requires a specific `--email` or `--user-id`. Same
  `-m` invocation as above; regenerates the token if the existing one has
  since expired (2-hour lifetime, much shorter than activation's 7 days),
  otherwise reuses it unchanged.

## Note (found and fixed 2026-08-08)

`populate_new_slide_thumbnails.py` and `generate_2048_png_thumbnails.py`
both import `openslide`/`tiffslide`, but `../backend/requirements.txt`
and `../backend/Dockerfile` were missing `openslide-python`/`tiffslide`/
`libopenslide0` entirely (unlike the sibling `omero-mvls` repo). Both
imports were silently failing and falling back to `None` in the real
container - thumbnail generation via OpenSlide/TiffSlide likely never
worked here. Fixed: both added, verified by building the image and
confirming `import openslide`/`import tiffslide` succeed.
