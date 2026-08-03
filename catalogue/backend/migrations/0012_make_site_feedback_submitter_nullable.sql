-- site_feedback used to require login (vmcRequireLogin() on the
-- frontend, require_user on the backend), so submitter_username was
-- always populated from the session. Opening the form to anonymous
-- visitors too means there's no session to read a username from -
-- NULL there just means "anonymous submitter", not a data-integrity
-- problem.
--
-- Run against your catalogue database, e.g.:
--   docker exec -i <mariadb_container> mariadb -u <app_user> -p'...' <database> \
--     < 0012_make_site_feedback_submitter_nullable.sql

ALTER TABLE site_feedback
  MODIFY COLUMN submitter_username VARCHAR(191) NULL COMMENT 'Username of the user who submitted this feedback, captured at submission time - NULL for anonymous (not logged in) submissions.';
