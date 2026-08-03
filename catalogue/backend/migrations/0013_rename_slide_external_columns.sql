-- slides.dih_image_hash/dih_checked_at (added in 0005/0006) were named after
-- a specific external system this catalogue project no longer names in
-- public-facing content. Renamed here to generic, source-agnostic names -
-- the underlying data and meaning are unchanged: still a content hash from
-- whatever external source-of-truth database a slide was optionally linked
-- to during import, and the timestamp such a lookup was last attempted.
--
-- Deliberately a rename via CHANGE COLUMN in a new migration rather than
-- editing 0005/0006's ADD COLUMN statements in place - a fresh deploy
-- replaying the full migration chain must reach the exact same end state as
-- a deployment that already ran 0005/0006 under the old names and then
-- applies this migration on top.
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0013_rename_slide_external_columns.sql

ALTER TABLE slides
  CHANGE COLUMN dih_image_hash external_image_hash VARCHAR(255) DEFAULT NULL
  COMMENT 'Content-identifying hash from an external source-of-truth database this slide was linked to during import, when the importing tool supports that. NULL for slides imported without an external match, and for slides imported before this column existed.'
  AFTER source,
  CHANGE COLUMN dih_checked_at external_checked_at TIMESTAMP NULL DEFAULT NULL
  COMMENT 'When an external source-of-truth lookup was last attempted for this slide during import, regardless of whether a match was found. NULL means no such lookup was ever attempted (e.g. imported by a tool with no external-lookup step at all).'
  AFTER external_image_hash,
  RENAME KEY uq_slides_dih_image_hash TO uq_slides_external_image_hash;

-- Comment-only cleanup for columns whose live COMMENT text (set by earlier
-- migrations) still names the same external system - no data/type change,
-- restates each column's existing definition exactly except for the comment.
ALTER TABLE annotation_contributors
  MODIFY COLUMN source_system varchar(100) DEFAULT NULL
  COMMENT 'Which legacy/source system this contributor record came from (e.g. an external slide-management database).';

ALTER TABLE slide_annotations
  MODIFY COLUMN zoom double NOT NULL
  COMMENT 'View-scale factor recorded at the time the annotation was drawn by the source system; whether coordinates need multiplying by this to reach full-resolution pixels is still being verified.',
  MODIFY COLUMN source_annotation_id int(11) DEFAULT NULL
  COMMENT 'Original identifier from the external source system this annotation was imported from, for provenance/audit; NULL for annotations created directly in the app.';

ALTER TABLE slide_annotations
  COMMENT='Region/point/line annotations attached to a slide - imported from an external source system (source_annotation_id preserves the original identifier from that system), or created directly by the app going forward.';

ALTER TABLE slides
  MODIFY COLUMN ingestion_method varchar(64) DEFAULT NULL
  COMMENT 'How this slide entered the catalogue - e.g. an importing tool''s own name, manual_donation_entry, legacy_crawler_v103. Free-text, no enforced list - new ingestion methods are expected over time.';

ALTER TABLE provenance_records
  MODIFY COLUMN origin_description TEXT DEFAULT NULL
  COMMENT 'Free-text description of where/how slides under this record entered the collection - often copied directly from the importing tool''s own report-only provenance questions.';
