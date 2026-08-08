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
| `populate_new_slide_thumbnails.py` | Generates thumbnails for every slide in the database that doesn't have one yet (e.g. after a fresh import batch) - same OpenSlide/TiffSlide approach, safe to re-run. Slides where automated generation fails (multi-scene/multiview files) are written to a report for manual follow-up instead of silently skipped. | `../docs/thumbnail-maintenance.md` |
| `export_annotations_ome_xml.py` | Generates one OME-XML file per slide with stored annotations, straight from the database - no QuPath round-trip. Offline/archival equivalent of the "Download annotations (OME-XML)" button on a slide's own page. | Own header docstring; user-facing equivalent documented in `../frontend/documents/script_annotation.html` |

## Related, not in this directory

- `../backend/app/sync_manual_thumbnails.py` - the second half of the
  manual thumbnail workflow (picks up PNGs dropped in
  `manual_thumbnails/`). Runs *inside* the `catalogue_backend` container,
  not from here directly - see `../docs/thumbnail-maintenance.md`.
- `../backend/app/backup_catalogue.py` - triggered via the admin-only
  `POST /api/admin/backup` endpoint, not run standalone.

## Note (found and fixed 2026-08-08)

`populate_new_slide_thumbnails.py` and `generate_2048_png_thumbnails.py`
both import `openslide`/`tiffslide`, but `../backend/requirements.txt`
and `../backend/Dockerfile` were missing `openslide-python`/`tiffslide`/
`libopenslide0` entirely (unlike the sibling `omero-mvls` repo). Both
imports were silently failing and falling back to `None` in the real
container - thumbnail generation via OpenSlide/TiffSlide likely never
worked here. Fixed: both added, verified by building the image and
confirming `import openslide`/`import tiffslide` succeed.
