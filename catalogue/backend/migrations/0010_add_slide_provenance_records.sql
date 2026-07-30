-- Adds a proper linked provenance/copyright table, rather than more flat
-- columns on slides. This supersedes the flat-column approach for anything
-- copyright-related (0009_add_slide_provenance.sql's provenance_origin/
-- provenance_date/provenance_original_path/provenance_notes stay as-is -
-- those cover per-slide history/frozen-path facts, a different concern from
-- what this table is for).
--
-- Why a separate table rather than more columns on slides: copyright/rights
-- information is naturally shared by a whole set of slides at once (e.g.
-- "everything from this share = held by the same institution"), not a
-- per-slide fact. A linked table means:
--   - no duplicating the same institution/copyright text across thousands
--     of slide rows
--   - a rights-status change affecting a whole batch is a single-row
--     UPDATE on provenance_records, not a mass rewrite of slides
--   - the same institution/department can still be split by finer-grained
--     rights differences when needed (e.g. human vs animal specimens under
--     the same department carrying different copyright terms) - just
--     create another provenance_records row and repoint the affected
--     slides.provenance_id at it; nothing about the schema needs to change
--     to support that split later.
--
-- Deliberately not fully fleshed out - the user's own framing was that this
-- table's exact shape will likely be redrawn as real needs emerge. This is
-- a reasonable starting point covering what's known now: institution,
-- department, specimen category, copyright holder, rights notes, and a
-- free-text origin description.
--
-- slides.provenance_id is nullable and NOT backfilled by this migration -
-- assigning existing (or this repo's own) slides to a real provenance
-- record requires knowing the actual institution/department/rights
-- breakdown, which is a curatorial decision, not something a schema
-- migration should invent. (Contrast with omero-mvls's own copy of this
-- migration, which does backfill - every existing row there really is one
-- batch, "MVLS Archive" / University of Glasgow, so that backfill is a
-- straightforward fact rather than a guess - but that's institution-specific
-- and deliberately doesn't belong in this de-branded, public repo.)
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0010_add_slide_provenance_records.sql

CREATE TABLE provenance_records (
  provenance_id INT NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  label VARCHAR(255) NOT NULL COMMENT 'Short human-readable identifier shown when selecting an existing record during import, e.g. "University of Glasgow - MVLS Archive".',
  institution VARCHAR(255) DEFAULT NULL COMMENT 'Institution this record is attributed to.',
  department VARCHAR(255) DEFAULT NULL COMMENT 'Department/collection within the institution, if applicable.',
  specimen_category VARCHAR(100) DEFAULT NULL COMMENT 'Specimen category this record applies to, if rights differ by category within the same institution/department, e.g. "human", "animal".',
  copyright_holder VARCHAR(255) DEFAULT NULL COMMENT 'Who holds copyright for slides under this record - often the institution, but can differ (e.g. a donor retaining rights).',
  rights_notes TEXT DEFAULT NULL COMMENT 'Free-text rights/copyright terms, conditions, or embargoes.',
  origin_description TEXT DEFAULT NULL COMMENT 'Free-text description of where/how slides under this record entered the collection - often copied directly from dih-slide-reconciler''s own report-only provenance questions.',
  created_date TIMESTAMP NULL DEFAULT current_timestamp() COMMENT 'When this record was created.',
  PRIMARY KEY (provenance_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Provenance and copyright records - one row can be shared by many slides (see slides.provenance_id), so a rights change affecting a whole batch is a single update here rather than a rewrite of every slide row.';

ALTER TABLE slides
  ADD COLUMN provenance_id INT NULL
  COMMENT 'Links to provenance_records.provenance_id - many slides can share one record. NULL until curated.'
  AFTER provenance_notes,
  ADD CONSTRAINT fk_slides_provenance FOREIGN KEY (provenance_id) REFERENCES provenance_records (provenance_id);
