-- dih-slide-reconciler currently has no way to tell it's already imported a given
-- file - it unconditionally crawls a folder and writes an INSERT for every slide
-- found, and slides.filename has no uniqueness constraint. Re-running it, or
-- running it against a share that partially overlaps with a previous run, would
-- create duplicate slides rows.
--
-- This column is the provenance half of the fix: reconcile.py's new --source flag
-- writes a free-text label here (e.g. "MVLS Archive", "Vet share batch 1")
-- describing which run/folder/query populated the row. The other half - the
-- actual dedup check - compares archive_relative_path (not physical_path, which
-- is mount-prefix-dependent and can differ across machines/runs for the same
-- physical file) against what's already in the target catalogue before crawling.
--
-- Existing rows all came from the one folder reconciled so far, so they're
-- backfilled accordingly rather than left blank.
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0004_add_slide_source.sql

ALTER TABLE slides
  ADD COLUMN source VARCHAR(255) NOT NULL DEFAULT ''
  COMMENT 'Free-text label describing which reconciler run/folder/query populated this row (e.g. "MVLS Archive", "Vet share batch 1") - set via reconcile.py --source and used to scope re-runs against archive_relative_path; not a uniqueness key itself.'
  AFTER archive_relative_path;

UPDATE slides SET source = 'MVLS Archive' WHERE source = '';
