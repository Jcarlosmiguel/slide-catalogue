-- A separate crawler tool is planned for archive folders that have no dih
-- coverage at all - it will write into these same slides/slide_metadata/
-- slide_technical_metadata tables, just like dih-slide-reconciler does, but
-- never even attempts a dih lookup.
--
-- Without this column, a row imported by that no-DIH crawler and a
-- share-only row from dih-slide-reconciler (dih was checked, no match
-- found) are indistinguishable - both have dih_image_hash NULL. That
-- matters for the same reason the dedup logic added earlier matters: if a
-- folder the no-DIH crawler already covered later turns out to have real
-- dih coverage, you need a reliable way to find exactly the rows that were
-- never actually checked, so a future dih-slide-reconciler pass can target
-- them for enrichment instead of either re-scanning everything or silently
-- skipping them forever (today's dedup only keys off archive_relative_path,
-- which can't tell "already imported, never checked" from "already
-- imported, checked and confirmed no match").
--
-- NULL = never checked against dih (e.g. the future no-DIH crawler's own
-- rows). A timestamp = dih-slide-reconciler processed this file at that
-- time, whether or not a match was found. Existing rows were all imported
-- by dih-slide-reconciler, so they're backfilled from their own
-- created_date as the best available proxy for when that check happened.
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0006_add_slide_dih_checked_at.sql

ALTER TABLE slides
  ADD COLUMN dih_checked_at TIMESTAMP NULL DEFAULT NULL
  COMMENT 'When dih-slide-reconciler last attempted a dih lookup for this slide, regardless of whether a match was found - NULL means dih has never been checked at all (e.g. imported by a no-DIH crawler). Distinct from dih_image_hash, which is only set when a match was actually found.'
  AFTER dih_image_hash;

UPDATE slides SET dih_checked_at = created_date WHERE dih_checked_at IS NULL;
