-- dih.location_index.image_hash is the actual join key dih-slide-reconciler
-- already uses throughout its own matching/annotation lookups (see
-- reconciler/dih_source.py - load_annotations(conn, image_hash), the
-- metadata_values joins, etc.) and is UNIQUE in dih's own schema
-- (`UNIQUE KEY image_hash (image_hash)` on location_index). Until now it was
-- only ever embedded as free text inside slide_metadata.notes
-- ("...image_hash=XXXX..."), so going back to dih to check provenance meant
-- parsing that string by hand. This column makes it a first-class,
-- queryable field instead.
--
-- NULL for slides with no dih match (share-only) and, for now, for every
-- slide imported before this column existed - there's no reliable way to
-- recover the original image_hash for those from data already in this
-- database (this deployment's own notes column is NULL for all existing
-- rows, from an earlier version of the reconciler). New imports populate it
-- going forward.
--
-- UNIQUE (not just indexed): each dih record should only ever be linked to
-- one real slide by design, so a duplicate would indicate an actual
-- reconciliation bug worth catching, not a legitimate case. MariaDB unique
-- keys allow any number of NULLs, so this doesn't conflict with the many
-- share-only/pre-existing rows that will have none.
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0005_add_slide_dih_image_hash.sql

ALTER TABLE slides
  ADD COLUMN dih_image_hash VARCHAR(255) DEFAULT NULL
  COMMENT 'dih.location_index.image_hash for the dih record this slide was linked to (dih-slide-reconciler --target-db-* imports only) - lets you go back to the dih database directly for provenance. NULL for share-only slides with no dih match, and for slides imported before this column existed.'
  AFTER source,
  ADD UNIQUE KEY uq_slides_dih_image_hash (dih_image_hash);
