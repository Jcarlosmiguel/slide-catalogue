-- Adds 'reviewer' and 'expert' user roles, a role_permissions table driving
-- authorization for their new capabilities (not hardcoded in Python), and a
-- slide_expert_notes table for direct expert-authored notes (the existing
-- "Expert contributor notes" section was previously read-only, sourced only
-- from the historical David Jenkinson import).
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0001_reviewer_expert_roles.sql

ALTER TABLE users
  MODIFY COLUMN role ENUM('user','admin','system_admin','reviewer','expert')
  NOT NULL DEFAULT 'user';

CREATE TABLE IF NOT EXISTS role_permissions (
  role VARCHAR(50) NOT NULL,
  permission_key VARCHAR(100) NOT NULL,
  PRIMARY KEY (role, permission_key)
);

INSERT IGNORE INTO role_permissions (role, permission_key) VALUES
  ('reviewer', 'corrections.view'),
  ('reviewer', 'corrections.review'),
  ('expert', 'expert_notes.write'),
  ('admin', 'corrections.view'),
  ('admin', 'corrections.review'),
  ('admin', 'expert_notes.write'),
  ('system_admin', 'corrections.view'),
  ('system_admin', 'corrections.review'),
  ('system_admin', 'expert_notes.write');

CREATE TABLE IF NOT EXISTS slide_expert_notes (
  note_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  slide_id BIGINT NOT NULL,
  author_username VARCHAR(191) NOT NULL,
  author_display_name VARCHAR(255),
  note_title VARCHAR(255),
  note_text TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_slide_expert_notes_slide (slide_id)
);
