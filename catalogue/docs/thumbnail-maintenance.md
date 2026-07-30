# Catalogue Thumbnail Maintenance

## Purpose

The Catalogue uses a two-stage thumbnail workflow:

1. Generate cropped PNG thumbnails directly from slide files.
2. Synchronise those PNG thumbnails into the catalogue thumbnail hierarchy.

This workflow allows thumbnails to be automatically generated, manually reviewed if required, and then published to the catalogue.

---

# Thumbnail Workflow Overview

```text
Slides
   ↓
generate_2048_png_thumbnails.py
   ↓
manual_thumbnails/
   ↓
(Optional manual editing)
   ↓
sync_manual_thumbnails.py
   ↓
thumbnails/2048/
thumbnails/1024/
thumbnails/512/
```

---

# New Slides - First-Time Thumbnails (e.g. after a dih-slide-reconciler import)

Script:

```text
catalogue/tools/populate_new_slide_thumbnails.py
```

Purpose:

- Query the catalogue database directly for every `ACTIVE` slide.
- Skip any slide that already has a `thumbnails/2048/{slide_id}.jpg`.
- For everything else, open the slide (OpenSlide first, TiffSlide fallback,
  same whitespace-crop approach as `generate_2048_png_thumbnails.py`) and
  write all three sizes straight into `thumbnails/2048/`, `thumbnails/1024/`,
  `thumbnails/512/`, keyed by the real `slide_id` - no `manual_thumbnails/`
  staging needed for the slides this succeeds on.
- Write a report of slides where automated generation failed - commonly
  multi-scene/multiview files where OpenSlide can't reliably pick which
  image represents the slide.

This is distinct from `sync_manual_thumbnails.py` below: that script expects
an *existing* thumbnail to back up and replace (or, as of the fix
described in Stage 3, is fine either way) - this one is specifically for
slides that have never had a thumbnail at all. Safe to re-run any time -
already-thumbnailed slides are always skipped.

Example:

```bash
python3 catalogue/tools/populate_new_slide_thumbnails.py \
  --db-host 127.0.0.1 --db-user catalogue_app --db-password '...' \
  --db-database catalogue \
  --thumbnails-root catalogue/thumbnails \
  --failed-report failed_thumbnails.txt
```

For every slide in the failed report: open it in QuPath, export a thumbnail
PNG, save it as `manual_thumbnails/{slide_id}.png`, then run
`sync_manual_thumbnails.py` (Stage 3 below) to pick it up - it now handles
both "replace an existing thumbnail" and "create a first one" the same way.

---

# Stage 1 - Generate PNG Thumbnails from Slides

Script:

```text
backend/tools/generate_2048_png_thumbnails.py
```

Purpose:

- Recursively scan a slide archive.
- Open slides using OpenSlide or TiffSlide.
- Generate large thumbnails.
- Automatically crop surrounding whitespace.
- Save cropped PNG thumbnails.

---

## Supported Formats

The generator currently supports:

```text
.ndpi
.scn
.svs
.mrxs
.vms
.vmu
.tif
.tiff
```

OpenSlide is used first.

TiffSlide is used as a fallback.

---

## Required Parameters

The script requires:

1. Source slide folder.
2. Output thumbnail folder.

Example:

```bash
python3 backend/tools/generate_2048_png_thumbnails.py \
"/mnt/virtual-microscopy" \
manual_thumbnails
```

---

## Crop Threshold

The crop threshold controls how aggressively white background is removed.

Default:

```text
245
```

Example:

```bash
python3 backend/tools/generate_2048_png_thumbnails.py \
"/mnt/virtual-microscopy" \
manual_thumbnails \
--threshold 250
```

Suggested values:

```text
235  Conservative cropping
245  Default
250  Aggressive cropping
```

If tissue is being cropped away, reduce the threshold.

If excessive white background remains, increase the threshold.

---

## Output

The script creates PNG files using the original slide filename.

Example:

```text
Oral_Biology_22.scn
```

becomes:

```text
manual_thumbnails/Oral_Biology_22.png
```

Existing PNG files are skipped.

---

# Stage 2 - Optional Manual Thumbnail Editing

Generated thumbnails may be reviewed before publication.

Examples:

- Additional cropping.
- Contrast adjustment.
- Rotation.
- Replacement with a manually curated thumbnail.

Modified files should remain in:

```text
manual_thumbnails/
```

and retain PNG format.

---

# Stage 3 - Synchronise Catalogue Thumbnails

Script:

```text
backend/app/sync_manual_thumbnails.py
```

Purpose:
Note: this script needs to run inside docker compose
- Read PNG files from:

```text
manual_thumbnails/
```

- If a thumbnail already exists for that slide ID, back it up first;
  otherwise (a slide with no thumbnail at all yet) skip straight to
  creating one - no existing file is required.
- Create the standard catalogue thumbnail hierarchy.

---

## Preparing a Manual Replacement Thumbnail

To manually replace an existing catalogue thumbnail:

1. Identify the catalogue slide ID.
2. Create or edit a PNG thumbnail. QuPath is highly recomended
3. Save the file using the slide ID.

Example:

```text
2920.png
```

4. Copy the file into:

```text
manual_thumbnails/
```

---

## Running the Synchronisation

Run:

```bash
docker exec -it catalogue_backend python3 /app/app/sync_manual_thumbnails.py
```

---

## Successful Processing

The script will:

- Verify the slide already has thumbnails.
- Back up existing thumbnails.
- Generate replacement thumbnails.
- Create:

```text
thumbnails/2048/
thumbnails/1024/
thumbnails/512/
```

- Remove the source PNG from:

```text
manual_thumbnails/
```

- Write a log entry.

---

## Expected Naming Convention

PNG thumbnails intended for synchronisation must use the slide identifier.

Example:

```text
2920.png
```

This updates:

```text
thumbnails/2048/2920.jpg
thumbnails/1024/2920.jpg
thumbnails/512/2920.jpg
```

---

## No Work Pending

If no PNG files exist in:

```text
manual_thumbnails/
```

the synchronisation script reports that there is nothing to process.

---

## Error Conditions

If a slide identifier cannot be matched:

```text
No thumbnails are modified.
```

The PNG file remains in:

```text
manual_thumbnails/
```

for investigation.

---

# Logs

Thumbnail synchronisation activity is recorded in the thumbnail maintenance log.

Review logs after large updates or before production releases.

---

# Backups

Original thumbnails are stored in:

```text
thumbnail_backups/
```

before replacement occurs.

This allows previous thumbnail sets to be restored if required.

---

# Git Policy

Version Controlled:

```text
tools/generate_2048_png_thumbnails.py
tools/populate_new_slide_thumbnails.py
backend/app/sync_manual_thumbnails.py
docs/thumbnail-maintenance.md
```

Not Version Controlled:

```text
manual_thumbnails/
thumbnails/
thumbnail_backups/
```

These folders contain generated image data and can be recreated.

---

# Recommended Workflow

Generate thumbnails:

```bash
python3 backend/tools/generate_2048_png_thumbnails.py \
"/mnt/virtual-microscopy" \
manual_thumbnails
```

Review thumbnails if required:

```text
manual_thumbnails/
```

Synchronise to catalogue format:

```bash
docker exec -it catalogue_backend python3 /app/app/sync_manual_thumbnails.py
```

Verify results:

```text
thumbnails/2048/
thumbnails/1024/
thumbnails/512/
```

The thumbnails are now ready for use by the Virtual Microscopy Catalogue.
