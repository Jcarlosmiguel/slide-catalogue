-- Backs the sysadmin "Import Batches" web workflow: upload a matching
-- .sql/.report.txt/.run.log trio (see catalogue/docs/import-batches.md
-- for the exact expected file shapes), resolve any ambiguous filenames
-- against real files on disk, record provenance, then commit as one
-- atomic import with fresh slide_ids.
--
-- import_batches is one row per upload. Uploaded files are stored on disk
-- under catalogue/import_batches/{batch_id}/ (mounted into catalogue_backend
-- at /srv/import_batches), not in the database - matching how backups
-- already work (catalogue/backups/database/full, not a BLOB column).
--
-- Run against slide_catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' slide_catalogue \
--     < 0015_add_import_batches.sql

CREATE TABLE import_batches (
  batch_id INT NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  status VARCHAR(32) NOT NULL DEFAULT 'awaiting_resolution' COMMENT 'awaiting_resolution -> ready -> committing -> committed | failed | cancelled.',
  uploaded_by_user_id INT DEFAULT NULL COMMENT 'users.user_id at upload time - no FK, survives account deletion (same reasoning as admin_audit_log).',
  uploaded_by_username VARCHAR(255) NOT NULL COMMENT 'Denormalized so this stays readable if the account is later deleted or renamed.',
  uploaded_at TIMESTAMP NULL DEFAULT current_timestamp() COMMENT 'When the three files were uploaded.',
  sql_filename VARCHAR(255) NOT NULL COMMENT 'Original filename of the uploaded .sql.',
  report_filename VARCHAR(255) NOT NULL COMMENT 'Original filename of the uploaded .report.txt.',
  run_log_filename VARCHAR(255) NOT NULL COMMENT 'Original filename of the uploaded .run.log.',
  storage_dir VARCHAR(255) NOT NULL COMMENT 'Subdirectory under /srv/import_batches holding the three files, e.g. "42".',
  archive_root_name VARCHAR(255) NULL COMMENT 'Basename of report.txt''s own "Crawled folder:" line - scopes disk-match lookups to this subtree of the mounted archive rather than searching the whole thing.',
  report_summary_json TEXT DEFAULT NULL COMMENT 'Parsed report.txt counts (linked/share-only/ambiguous/orphan totals, annotation author breakdown) for display without re-parsing the file on every page load.',
  provenance_id INT DEFAULT NULL COMMENT 'Set once the sysadmin records/selects origin information for this batch - links to provenance_records, same table every slide already uses.',
  imported_slide_ids TEXT DEFAULT NULL COMMENT 'JSON array of slide_id, populated at commit time - avoids re-deriving which slides belong to this batch later (e.g. for the thumbnail job).',
  skipped_ambiguous_count INT DEFAULT NULL COMMENT 'How many ambiguous files were resolved as "skipped" rather than imported - set at commit time.',
  error_message TEXT DEFAULT NULL COMMENT 'Set if status=failed - the exception message from the failed commit attempt.',
  committed_at TIMESTAMP NULL DEFAULT NULL COMMENT 'When the import transaction actually succeeded.',
  PRIMARY KEY (batch_id),
  CONSTRAINT fk_import_batches_provenance FOREIGN KEY (provenance_id) REFERENCES provenance_records (provenance_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='One row per completed crawler-tool upload processed through the sysadmin web import workflow.';

-- Backs the sysadmin-triggered background thumbnail-generation job (see
-- thumbnail_job.py) - a real, pollable background task, not the
-- fully-synchronous "block the HTTP request until done" pattern
-- POST /api/admin/backup uses. No task-queue infrastructure exists
-- anywhere in this app, and none is being introduced for this one
-- feature - see thumbnail_job.py's own module docstring for why a plain
-- threading.Thread is used instead. Progress must be persisted here
-- regardless of dispatch mechanism, since the polling GET request is a
-- separate HTTP request/thread from the one that started the job - there
-- is no in-memory object to hand it.
CREATE TABLE thumbnail_jobs (
  job_id INT NOT NULL AUTO_INCREMENT COMMENT 'Primary key, also the value polled via GET /api/admin/thumbnail-jobs/{job_id}.',
  batch_id INT DEFAULT NULL COMMENT 'The import batch this job was triggered for, if any - NULL for a job run manually against an arbitrary slide_id list.',
  status VARCHAR(32) NOT NULL DEFAULT 'queued' COMMENT 'queued | running | completed | failed.',
  total_slides INT NOT NULL COMMENT 'How many slide_ids this job was asked to process.',
  processed_slides INT NOT NULL DEFAULT 0 COMMENT 'Updated after each slide - the polling progress counter.',
  succeeded_slides INT NOT NULL DEFAULT 0 COMMENT 'Of processed_slides, how many actually got a thumbnail written.',
  manual_needed_detail_json TEXT DEFAULT NULL COMMENT 'JSON list of {slide_id, filename, physical_path, error} for slides automated generation could not handle - same manual-QuPath-export guidance as populate_new_slide_thumbnails.py''s own --failed-report list.',
  triggered_by_user_id INT DEFAULT NULL,
  triggered_by_username VARCHAR(255) NOT NULL,
  started_at TIMESTAMP NULL DEFAULT NULL,
  finished_at TIMESTAMP NULL DEFAULT NULL,
  error_message TEXT DEFAULT NULL COMMENT 'Set if status=failed for a reason outside normal per-slide failure (e.g. the whole job thread crashed).',
  created_at TIMESTAMP NULL DEFAULT current_timestamp(),
  PRIMARY KEY (job_id),
  CONSTRAINT fk_thumbnail_jobs_batch FOREIGN KEY (batch_id) REFERENCES import_batches (batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Background thumbnail-generation runs triggered from the sysadmin UI.';
