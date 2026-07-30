-- Currently the only record of where a slide came from is physical_path/
-- archive_relative_path - both live values, updated in place if a slide is
-- ever physically relocated (e.g. a future storage reorganisation). That
-- means the moment a reorganisation happens, the historical "where did this
-- come from and how did it get here" information is silently overwritten,
-- not just moved. These columns exist to survive that.
--
-- ingestion_method: short free-text label for *how* a slide entered the
-- catalogue - 'dih-slide-reconciler' for everything imported by that tool,
-- but deliberately not an enforced list, since future entry methods
-- (manual donation entry, other acquisition tools) aren't fully known yet.
--
-- provenance_origin: *where* a slide came from - institution/collection/
-- donor - independent of file location. For existing dih-slide-reconciler
-- imports this is effectively a copy of slides.source at the time of
-- import, but conceptually distinct: source is a batch/re-run-scoping label
-- the reconciler itself relies on, provenance_origin is a durable
-- description meant to still make sense years later regardless of what
-- source labelling convention any given tool used.
--
-- provenance_date: when a slide entered the collection (acquisition/
-- donation/original scan date), distinct from created_date (when the
-- database row itself was created, which can lag behind - e.g. a backlog of
-- donations catalogued together long after they were actually received).
--
-- provenance_original_path: a frozen snapshot of archive_relative_path taken
-- once at ingestion time, never updated again - this is the actual fix for
-- "we lose provenance if we reorganise storage": archive_relative_path can
-- change to reflect a slide's new location, but this column keeps showing
-- exactly where it was when it first entered the catalogue.
--
-- provenance_notes: free-text overflow for anything the structured fields
-- above don't capture (donor correspondence references, consent/rights
-- details, etc.).
--
-- Existing rows backfilled from the best available proxy for each: all
-- ~2,947 existing rows were imported by dih-slide-reconciler, so
-- ingestion_method is set accordingly; provenance_origin copies the
-- existing source value; provenance_date uses created_date (same proxy
-- already used for dih_checked_at in 0006_add_slide_dih_checked_at.sql);
-- provenance_original_path copies the current archive_relative_path, which
-- is still accurate today since no relocation has happened yet.
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0009_add_slide_provenance.sql

ALTER TABLE slides
  ADD COLUMN ingestion_method VARCHAR(64) NULL
  COMMENT 'How this slide entered the catalogue - e.g. dih-slide-reconciler, manual_donation_entry, legacy_crawler_v103. Free-text, no enforced list - new ingestion methods are expected over time.'
  AFTER is_available,
  ADD COLUMN provenance_origin VARCHAR(255) NULL
  COMMENT 'Where this slide came from - institution/collection/donor - independent of its current file location. Distinct from source, which is a batch/re-run-scoping label the reconciler relies on operationally.'
  AFTER ingestion_method,
  ADD COLUMN provenance_date DATE NULL
  COMMENT 'When this slide entered the collection (acquisition/donation/original scan date), distinct from created_date (when this database row was created, which can lag behind the real event).'
  AFTER provenance_origin,
  ADD COLUMN provenance_original_path TEXT NULL
  COMMENT 'Frozen snapshot of archive_relative_path taken once at ingestion - never updated afterwards, even if the slide is later physically relocated and archive_relative_path changes to match. Preserves where the file was when it first entered the catalogue.'
  AFTER provenance_date,
  ADD COLUMN provenance_notes TEXT NULL
  COMMENT 'Free-text provenance detail not captured by the structured fields above (donor correspondence references, consent/rights notes, etc.).'
  AFTER provenance_original_path;

UPDATE slides SET
  ingestion_method = 'dih-slide-reconciler',
  provenance_origin = source,
  provenance_date = DATE(created_date),
  provenance_original_path = archive_relative_path
WHERE ingestion_method IS NULL;
