-- An external source-of-truth database's own content-hash join key,
-- unique in that system's schema. Until now it was only ever embedded as
-- free text inside slide_metadata.notes, so going back to the external
-- system to check provenance meant parsing that string by hand. This
-- column makes it a first-class, queryable field instead.
--
-- Renamed from dih_image_hash to external_image_hash by a later migration
-- (0013_rename_slide_external_columns.sql) - this file is left as
-- originally applied, since a fresh deploy replaying the full chain must
-- reach the same end state as a deployment that already ran this migration
-- under the old name.
--
-- NULL for slides with no external match (share-only) and, for now, for
-- every slide imported before this column existed - there's no reliable
-- way to recover the original hash for those from data already in this
-- database. New imports populate it going forward.
--
-- UNIQUE (not just indexed): each external record should only ever be
-- linked to one real slide by design, so a duplicate would indicate an
-- actual reconciliation bug worth catching, not a legitimate case. MariaDB
-- unique keys allow any number of NULLs, so this doesn't conflict with the
-- many share-only/pre-existing rows that will have none.
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0005_add_slide_external_image_hash.sql

ALTER TABLE slides
  ADD COLUMN dih_image_hash VARCHAR(255) DEFAULT NULL
  COMMENT 'Content hash from an external source-of-truth database, for the record this slide was linked to during import. NULL for share-only slides with no external match, and for slides imported before this column existed.'
  AFTER source,
  ADD UNIQUE KEY uq_slides_dih_image_hash (dih_image_hash);
