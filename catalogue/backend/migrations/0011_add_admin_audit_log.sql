-- Audit trail for the new system_admin-only actions (POST /api/admin/backup,
-- POST /api/admin/sql) added alongside this migration. Only mutating
-- actions are logged (a triggered backup; an UPDATE/DELETE/INSERT/ALTER/
-- CREATE run through the SQL console) - plain SELECTs and read-only page
-- views are not, by design, to keep the log focused on things that could
-- need undoing.
--
-- user_id/username are both stored (not just a foreign key to users) so the
-- log stays readable even if the account that took an action is later
-- deleted or renamed - an audit trail that goes blank the moment its actor
-- is removed defeats the point.
--
-- No foreign key to users on purpose, for the same reason: deleting a user
-- must never be blocked by, or cascade into, their own audit history.
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0011_add_admin_audit_log.sql

CREATE TABLE admin_audit_log (
  audit_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NULL COMMENT 'users.user_id at the time of the action - no FK, survives account deletion.',
  username VARCHAR(255) NOT NULL COMMENT 'Denormalized so the log stays readable if the account is later deleted or renamed.',
  action VARCHAR(64) NOT NULL COMMENT 'e.g. backup, sql, audit_log_cleared.',
  detail TEXT NULL COMMENT 'e.g. the backup filename, or the exact SQL statement executed.',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_admin_audit_log_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
