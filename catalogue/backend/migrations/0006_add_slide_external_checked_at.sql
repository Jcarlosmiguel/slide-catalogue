-- A separate crawler tool is planned for archive folders that have no
-- external-database coverage at all - it will write into these same
-- slides/slide_metadata/slide_technical_metadata tables, just like a
-- reconciler-style importer does, but never even attempts an external
-- lookup.
--
-- Renamed from dih_checked_at to external_checked_at by a later migration
-- (0013_rename_slide_external_columns.sql) - this file is left as
-- originally applied, since a fresh deploy replaying the full chain must
-- reach the same end state as a deployment that already ran this migration
-- under the old name.
--
-- Without this column, a row imported by that no-lookup crawler and a
-- share-only row from a reconciler-style importer (external db was
-- checked, no match found) are indistinguishable - both have
-- dih_image_hash NULL. That matters for the same reason the dedup logic
-- added earlier matters: if a folder the no-lookup crawler already
-- covered later turns out to have real external-database coverage, you
-- need a reliable way to find exactly the rows that were never actually
-- checked, so a future reconciliation pass can target them for enrichment
-- instead of either re-scanning everything or silently skipping them
-- forever (today's dedup only keys off archive_relative_path, which can't
-- tell "already imported, never checked" from "already imported, checked
-- and confirmed no match").
--
-- NULL = never checked against an external database (e.g. the no-lookup
-- crawler's own rows). A timestamp = a reconciler-style importer processed
-- this file at that time, whether or not a match was found. Existing rows
-- were all imported that way, so they're backfilled from their own
-- created_date as the best available proxy for when that check happened.
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0006_add_slide_external_checked_at.sql

ALTER TABLE slides
  ADD COLUMN dih_checked_at TIMESTAMP NULL DEFAULT NULL
  COMMENT 'When an external source-of-truth lookup was last attempted for this slide, regardless of whether a match was found - NULL means it has never been checked at all (e.g. imported by a no-lookup crawler). Distinct from dih_image_hash, which is only set when a match was actually found.'
  AFTER dih_image_hash;

UPDATE slides SET dih_checked_at = created_date WHERE dih_checked_at IS NULL;
