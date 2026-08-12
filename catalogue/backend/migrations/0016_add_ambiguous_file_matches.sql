-- Ambiguous-file resolution for the Import Batches workflow (see
-- 0015_add_import_batches.sql). A crawler tool may report a filename as
-- ambiguous (matched more than one candidate location) without
-- auto-resolving it, leaving that to a human. Resolution happens per
-- REAL FILE FOUND ON DISK, not per report line - the same filename can
-- appear more than once in a report (once per real physical file sharing
-- that name), and 2-3 same-named files may be true duplicates or a
-- genuine collision, only distinguishable by comparing their actual
-- content/technical metadata.
--
-- Run against slide_catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' slide_catalogue \
--     < 0016_add_ambiguous_file_matches.sql

CREATE TABLE import_batch_ambiguous_files (
  ambiguous_id INT NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  batch_id INT NOT NULL COMMENT 'The batch this ambiguous file was reported under.',
  filename VARCHAR(255) NOT NULL COMMENT 'Basename only - one row per distinct ambiguous filename per batch, deduplicated at parse time across every report line sharing this name.',
  candidate_folders_json TEXT NOT NULL COMMENT 'JSON array of candidate folder_path strings this filename collided across, as listed in report.txt.',
  PRIMARY KEY (ambiguous_id),
  CONSTRAINT fk_import_batch_ambiguous_files_batch FOREIGN KEY (batch_id) REFERENCES import_batches (batch_id),
  INDEX idx_import_batch_ambiguous_files_batch (batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='One row per distinct ambiguous-filename entry parsed from an import batch''s report.txt.';

CREATE TABLE import_batch_ambiguous_file_matches (
  match_id INT NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  ambiguous_id INT NOT NULL COMMENT 'Which distinct ambiguous filename this real file matched.',
  relative_path TEXT NOT NULL COMMENT 'Path under the archive root, e.g. "Batch1/SomeFolder/slide.ndpi".',
  physical_path TEXT NOT NULL COMMENT 'Full path as slides.physical_path would store it - derived automatically from the real disk find, never hand-typed by the sysadmin.',
  file_size_bytes BIGINT NOT NULL,
  content_hash VARCHAR(64) NULL COMMENT 'SHA-256 of the lowest-resolution pyramid level only (see import_batches.py hash_lowest_pyramid_level) - NULL if hashing failed (corrupt/unsupported file - still shown, just without duplicate-detection).',
  width_pixels INT NULL COMMENT 'From OpenSlide/TiffSlide dimensions - NULL if the file could not be opened.',
  height_pixels INT NULL,
  slide_vendor VARCHAR(64) NULL COMMENT 'e.g. "hamamatsu", "leica" - from openslide.vendor/tiffslide.vendor properties.',
  objective_magnification VARCHAR(20) NULL COMMENT 'From openslide.objective-power, when present.',
  resolution VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT 'pending | unlinked | skipped. unlinked = import this file as a new slide with no prior annotation history; skipped = don''t import it.',
  resolved_by_user_id INT NULL,
  resolved_at TIMESTAMP NULL,
  PRIMARY KEY (match_id),
  CONSTRAINT fk_ambig_matches_ambiguous FOREIGN KEY (ambiguous_id) REFERENCES import_batch_ambiguous_files (ambiguous_id),
  INDEX idx_ambig_matches_ambiguous (ambiguous_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='One row per real file found on disk for an ambiguous filename - resolved independently, since 2-3 real files sharing a name may be true duplicates or a genuine collision.';
