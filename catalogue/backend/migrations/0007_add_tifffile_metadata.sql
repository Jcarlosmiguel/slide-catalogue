-- An importing crawler tool now runs every file through tifffile before
-- OpenSlide or TiffSlide even attempt it - both require a well-formed TIFF/BigTIFF
-- container for every vendor format this catalogue handles (NDPI, SCN,
-- SVS), so a file tifffile flags as unreadable is going to fail both of
-- them too. Without a column of its own, that check's result only ever
-- existed inside the crawler's own run - useful for that one run's asset
-- status decision, but invisible afterwards to anyone querying the
-- catalogue directly, and impossible to use for cross-run duplicate
-- detection (see tifffile_hash below).
--
-- Real-world finding this was built to fix: `asset_status='CORRUPT_FILE'`
-- was previously set whenever both OpenSlide and TiffSlide failed - but 8
-- real Z-stack NDPI files failed both for a completely different, non-
-- corrupt reason (TiffSlide's `.properties` can't build a pyramid-level
-- abstraction for a 4D shape; OpenSlide rejects the format outright) while
-- tifffile read them fine and real metadata was recovered for every one.
-- tifffile_status is now the authority `asset_status` decisions are based
-- on, with openslide_status/tiffslide_status kept purely for per-library
-- provenance.
--
-- tifffile_hash: a genuine content hash (SHA-256 of the raw, undecoded
-- bytes of each series' lowest-resolution pyramid level - never the full
-- file, confirmed necessary after a real 17GB+ archive file made full-
-- resolution hashing time out entirely), used for cross-run duplicate
-- detection (same slide rescanned, or saved twice under different
-- filenames/folders) via `asset_status='DUPLICATE_SLIDE'` and a
-- `slides_to_be_deleted_review` row - never auto-deleted, always left for
-- a human to confirm. Only matches duplicates within the same file format;
-- cross-format matching (e.g. the same slide as both NDPI and SVS) would
-- need a decoded-pixel hash instead and is out of scope for now.
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0007_add_tifffile_metadata.sql

ALTER TABLE slide_technical_metadata
  ADD COLUMN tifffile_status VARCHAR(32) NULL
  COMMENT 'tifffile container-structure check result reported by the crawler - the authority asset_status=CORRUPT_FILE decisions are based on.'
  AFTER z_spacing,
  ADD COLUMN tifffile_hash VARCHAR(64) NULL
  COMMENT 'SHA-256 of each series'' lowest-resolution pyramid level, raw undecoded bytes - a genuine content hash (not the full file, and not a metadata fingerprint), used for cross-run duplicate detection via slides_to_be_deleted_review. NULL when tifffile_status is not SUCCESS.'
  AFTER tifffile_status;
