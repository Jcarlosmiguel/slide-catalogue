# Manual Thumbnail Replacement

## Purpose

Replace existing catalogue thumbnails with manually curated versions.

The replacement process only updates existing slides and will not create
new thumbnail sets.

## Preparing a Thumbnail

1. Open the source slide.
2. Create a replacement thumbnail.
3. Save it as:

   <slide_id>.png

Example:

   2920.png

4. Copy the PNG into:

   manual_thumbnails/

## Running the Synchronisation

Run:

    docker exec mvls_catalogue_backend \
    python /app/app/sync_manual_thumbnails.py

## Successful Processing

The script will:

- Verify the slide already has a 2048 thumbnail.
- Back up existing thumbnails.
- Generate new 2048, 1024 and 512 JPG thumbnails.
- Delete the source PNG.
- Write a log entry.

Example:

    OK 2920

## No Work Pending

Example:

    INFO no PNG files found

## Error Conditions

Example:

    ERROR 99999 missing 2048 thumbnail

In this case:

- No thumbnails are modified.
- The PNG remains in manual_thumbnails/.
- The issue must be investigated manually.

## Logs

Log file location:

    thumbnail_backups/thumbnail_sync.log

View recent activity:

    tail -20 thumbnail_backups/thumbnail_sync.log

## Backups

Original thumbnails are stored in:

    thumbnail_backups/YYYY-MM-DD/<slide_id>/

Example:

    thumbnail_backups/2026-07-15/2920/
