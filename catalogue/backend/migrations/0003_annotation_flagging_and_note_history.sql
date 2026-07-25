-- 1. Lets an accepted "incorrect annotation" report actually stop the
--    annotation being shown, instead of only changing the correction's own
--    status (the app now sets/clears this automatically in
--    _update_correction_status based on the correction's current
--    status+verdict, so it stays reversible if a decision is reopened).
-- 2. Lets expert-role users edit the legacy contributor note
--    content directly (title/text), while preserving every prior version
--    in an audit table first - trusted, no approval step, but nothing is
--    silently lost if a change turns out to be wrong.
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0003_annotation_flagging_and_note_history.sql

ALTER TABLE slide_annotations
  ADD COLUMN flagged_incorrect TINYINT(1) NOT NULL DEFAULT 0
  COMMENT 'Set automatically when a slide_annotation-sourced correction reporting this annotation as incorrect is accepted; cleared if that decision is later reversed. Flagged annotations are excluded from the slide detail view.'
  AFTER invisible;

CREATE TABLE IF NOT EXISTS legacy_curation_edit_history (
  history_id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Primary key.',
  curation_id BIGINT NOT NULL COMMENT 'The legacy_curation.curation_id this history entry preserves a prior version of.',
  previous_annotation_title VARCHAR(500) COMMENT 'annotation_title value immediately before this edit.',
  previous_note_text LONGTEXT COMMENT 'note_text value immediately before this edit.',
  edited_by_username VARCHAR(191) NOT NULL COMMENT 'Username of the expert who made this edit.',
  edited_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'When this edit was made.',
  KEY idx_legacy_curation_edit_history_curation (curation_id)
) COMMENT='Audit trail of every edit an expert makes to a legacy_curation note - preserves the prior title/text before each overwrite.';
