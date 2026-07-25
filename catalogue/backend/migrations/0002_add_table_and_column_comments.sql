-- Documents every table and column in catalogue that was missing a
-- COMMENT (240 columns across 27 base tables, plus 17 table-level comments).
-- Generated from a live-schema survey so every MODIFY COLUMN preserves the
-- column's existing type/nullability/default/auto_increment exactly - only
-- the comment is added or changed. The two views (v_slide_catalogue_app,
-- v_slide_david_notes) are skipped: MariaDB views don't support per-column
-- comments.
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0002_add_table_and_column_comments.sql

ALTER TABLE `slides` COMMENT='Core catalogue record for one virtual slide file - one row per slide, joined by slide_id to slide_metadata, slide_technical_metadata, slide_annotations, and the various correction/feedback tables.';
ALTER TABLE `slide_metadata` COMMENT='Curated organ/species/stain/description metadata and generated thumbnail paths for a slide - one row per slide_id, distinct from the raw crawler-derived data in slide_technical_metadata.';
ALTER TABLE `slide_annotations` COMMENT='Region/point/line annotations attached to a slide - imported from the legacy Slidepath DIH database via dih-slide-reconciler (source_annotation_id preserves the original dih annotationId), or created directly by the app going forward.';
ALTER TABLE `slide_corrections` COMMENT='User-submitted feedback/correction reports awaiting admin or reviewer action - covers metadata corrections, reported annotation errors, and expert-note corrections, distinguished by feedback_source.';
ALTER TABLE `slide_correction_actions` COMMENT='Append-only audit log of actions taken against a slide_corrections row - one row per status change or applied metadata update.';
ALTER TABLE `users` COMMENT='Catalogue user accounts - local or LDAP-authenticated, with a role controlling what they can see and do (see role_permissions for reviewer/expert capabilities).';
ALTER TABLE `role_permissions` COMMENT='Maps each role to the permission keys it grants - drives require_permission() authorization checks for reviewer/expert capabilities, without hardcoding role names in application code.';
ALTER TABLE `slide_expert_notes` COMMENT='Notes written directly by expert-role users on a slide, shown in the \'Expert contributor notes\' section alongside (but separate from) the read-only historical David Jenkinson import.';
ALTER TABLE `access_requests` COMMENT='Self-service requests for catalogue access, reviewed by an admin before a user account is created.';
ALTER TABLE `access_request_blocked_attempts` COMMENT='Log of access requests rejected automatically before reaching the review queue (e.g. duplicate email already registered), kept for abuse monitoring.';
ALTER TABLE `annotation_contributors` COMMENT='Reference list of individuals credited as annotation contributors/authors in imported source data, for display and attribution.';
ALTER TABLE `david_record_slide_links` COMMENT='Reconciliation candidates/links between david_jenkinson_curation records and catalogue slides - a broader or earlier-stage table than the confirmed slide_david_annotations.';
ALTER TABLE `password_reset_log` COMMENT='Audit log of password-reset attempts, successful or not, for abuse monitoring and support troubleshooting.';
ALTER TABLE `password_reset_tokens` COMMENT='Single-use, time-limited tokens issued for the forgot-password flow.';
ALTER TABLE `user_activation_tokens` COMMENT='Single-use, time-limited tokens issued to newly-approved accounts to set their initial password and activate.';
ALTER TABLE `site_feedback` COMMENT='General free-text feedback about the catalogue site/UX, not tied to a specific slide or correction - distinct from slide_corrections.';
ALTER TABLE `system_settings` COMMENT='Simple key-value store for admin-configurable application settings.';
ALTER TABLE `slides`
  MODIFY COLUMN `slide_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key, referenced by nearly every other slide-scoped table.',
  MODIFY COLUMN `inventory_id` bigint(20) NULL DEFAULT NULL COMMENT 'Legacy identifier from the pre-catalogue crawler inventory, kept for provenance/cross-referencing with older exports.',
  MODIFY COLUMN `filename` text NOT NULL COMMENT 'The slide\'s own filename as found on disk (not necessarily unique across the archive).',
  MODIFY COLUMN `physical_path` text NOT NULL COMMENT 'Full server-side filesystem path used by the application to open the slide file directly.',
  MODIFY COLUMN `archive_relative_path` text NULL DEFAULT NULL COMMENT 'Path relative to the archive share root (e.g. "Archive/..."), used to build share links for different OS mount points.',
  MODIFY COLUMN `slide_format` varchar(20) NULL DEFAULT NULL COMMENT 'File extension/format of the slide (e.g. NDPI, SCN, SVS).',
  MODIFY COLUMN `file_size_bytes` bigint(20) NULL DEFAULT NULL COMMENT 'Size of the slide file on disk, in bytes.',
  MODIFY COLUMN `width_pixels` int(11) NULL DEFAULT NULL COMMENT 'Full-resolution (level 0) pixel width of the slide image.',
  MODIFY COLUMN `height_pixels` int(11) NULL DEFAULT NULL COMMENT 'Full-resolution (level 0) pixel height of the slide image.',
  MODIFY COLUMN `metadata_status` enum('MATCHED_METADATA','NO_METADATA') NOT NULL COMMENT 'Whether this slide has been matched to curated metadata (MATCHED_METADATA) or still needs it (NO_METADATA).',
  MODIFY COLUMN `created_date` timestamp NULL DEFAULT current_timestamp() COMMENT 'When this slide record was first inserted into the catalogue.';
ALTER TABLE `slide_metadata`
  MODIFY COLUMN `slide_id` bigint(20) NOT NULL COMMENT 'Slide this metadata belongs to (slides.slide_id).',
  MODIFY COLUMN `organ` varchar(255) NULL DEFAULT NULL COMMENT 'Curated organ or anatomical structure for this slide.',
  MODIFY COLUMN `species` varchar(255) NULL DEFAULT NULL COMMENT 'Curated species for this slide.',
  MODIFY COLUMN `stain` varchar(255) NULL DEFAULT NULL COMMENT 'Curated (or raw, pre-normalisation) stain description for this slide.',
  MODIFY COLUMN `magnification` int(11) NULL DEFAULT NULL COMMENT 'Curated primary objective magnification for this slide.',
  MODIFY COLUMN `description` text NULL DEFAULT NULL COMMENT 'Free-text description of the slide\'s content.',
  MODIFY COLUMN `notes` text NULL DEFAULT NULL COMMENT 'Free-text curator notes.',
  MODIFY COLUMN `created_date` timestamp NULL DEFAULT current_timestamp() COMMENT 'Row creation timestamp.',
  MODIFY COLUMN `updated_date` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp() COMMENT 'Row last-updated timestamp.';
ALTER TABLE `species_dictionary`
  MODIFY COLUMN `species_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  MODIFY COLUMN `species_name` varchar(255) NOT NULL COMMENT 'Raw/original species name as it appears in source data before normalisation.',
  MODIFY COLUMN `scientific_name` varchar(255) NULL DEFAULT NULL COMMENT 'Latin binomial/scientific name for this species.',
  MODIFY COLUMN `active` tinyint(1) NULL DEFAULT 1 COMMENT 'Whether this dictionary entry is currently in active use (0 = retired/superseded).',
  MODIFY COLUMN `notes` text NULL DEFAULT NULL COMMENT 'Free-text curator notes.',
  MODIFY COLUMN `canonical_species` varchar(255) NULL DEFAULT NULL COMMENT 'Preferred canonical species name.',
  MODIFY COLUMN `species_group` varchar(255) NULL DEFAULT NULL COMMENT 'Broad grouping used for search and reconciliation (e.g. mammal, avian).',
  MODIFY COLUMN `normalisation_status` varchar(50) NULL DEFAULT NULL COMMENT 'Status of dictionary normalisation, e.g. NORMALISED, REVIEW, EXCLUDED.',
  MODIFY COLUMN `also_known_as` text NULL DEFAULT NULL COMMENT 'Comma-separated aliases, abbreviations, spelling variants, or legacy labels.',
  MODIFY COLUMN `review_status` varchar(50) NULL DEFAULT NULL COMMENT 'Dictionary curation status, e.g. APPROVED, PENDING, REVIEW.',
  MODIFY COLUMN `confidence` varchar(20) NULL DEFAULT NULL COMMENT 'Confidence in the canonical mapping, e.g. HIGH, MEDIUM, LOW.';
ALTER TABLE `organ_dictionary`
  MODIFY COLUMN `organ_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  MODIFY COLUMN `organ_name` varchar(255) NOT NULL COMMENT 'Raw/original organ name as it appears in source data before normalisation.',
  MODIFY COLUMN `organ_system` varchar(255) NULL DEFAULT NULL COMMENT 'Broader body system this organ belongs to (e.g. Cardiovascular, Respiratory).',
  MODIFY COLUMN `active` tinyint(1) NULL DEFAULT 1 COMMENT 'Whether this dictionary entry is currently in active use (0 = retired/superseded).',
  MODIFY COLUMN `notes` text NULL DEFAULT NULL COMMENT 'Free-text curator notes.';
ALTER TABLE `tissue_dictionary`
  MODIFY COLUMN `tissue_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  MODIFY COLUMN `tissue_name` varchar(255) NOT NULL COMMENT 'Raw/original tissue name as it appears in source data before normalisation.',
  MODIFY COLUMN `tissue_category` varchar(255) NULL DEFAULT NULL COMMENT 'Broader histological category this tissue belongs to.',
  MODIFY COLUMN `active` tinyint(1) NULL DEFAULT 1 COMMENT 'Whether this dictionary entry is currently in active use (0 = retired/superseded).',
  MODIFY COLUMN `notes` text NULL DEFAULT NULL COMMENT 'Free-text curator notes.';
ALTER TABLE `organ_tissue_dictionary`
  MODIFY COLUMN `organ_id` int(11) NOT NULL COMMENT 'Organ side of the relationship (organ_dictionary.organ_id).',
  MODIFY COLUMN `tissue_id` int(11) NOT NULL COMMENT 'Tissue side of the relationship (tissue_dictionary.tissue_id).',
  MODIFY COLUMN `notes` text NULL DEFAULT NULL COMMENT 'Free-text curator notes.';
ALTER TABLE `david_jenkinson_curation`
  MODIFY COLUMN `curation_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.';
ALTER TABLE `slide_david_annotations`
  MODIFY COLUMN `created_at` timestamp NULL DEFAULT current_timestamp() COMMENT 'When this reconciliation link was created.';
ALTER TABLE `slide_tissue_annotations`
  MODIFY COLUMN `created_date` timestamp NULL DEFAULT current_timestamp() COMMENT 'When this slide-tissue assignment was created.';
ALTER TABLE `duplicate_slide_mapping`
  MODIFY COLUMN `duplicate_slide_id` bigint(20) NOT NULL COMMENT 'The slides.slide_id identified as a duplicate.',
  MODIFY COLUMN `canonical_slide_id` bigint(20) NOT NULL COMMENT 'The slides.slide_id this duplicate should be treated as equivalent to.',
  MODIFY COLUMN `duplicate_crawler_id` bigint(20) NULL DEFAULT NULL COMMENT 'Crawler-assigned identifier for the duplicate file, kept for provenance.',
  MODIFY COLUMN `reason` varchar(255) NULL DEFAULT NULL COMMENT 'Why this slide was flagged as a duplicate.',
  MODIFY COLUMN `evidence` text NULL DEFAULT NULL COMMENT 'Free-text supporting evidence for the duplicate determination.',
  MODIFY COLUMN `created_date` timestamp NULL DEFAULT current_timestamp() COMMENT 'When this mapping was recorded.';
ALTER TABLE `slide_annotations`
  MODIFY COLUMN `annotation_id` bigint(20) NOT NULL COMMENT 'Primary key; reuses dih\'s own annotationId for imported rows so it\'s a stable global identifier.',
  MODIFY COLUMN `slide_id` bigint(20) NOT NULL COMMENT 'Slide this annotation belongs to (slides.slide_id).',
  MODIFY COLUMN `annotation_type` varchar(128) NOT NULL COMMENT 'Shape/kind of annotation (e.g. rectangle, ellipse, arrow, measure, pin, drawing, polygon, scanned_region).',
  MODIFY COLUMN `rect_x` int(11) NOT NULL DEFAULT -1 COMMENT 'Bounding rectangle (or ellipse bounding box) X coordinate; -1 when not applicable to this annotation_type.',
  MODIFY COLUMN `rect_y` int(11) NOT NULL DEFAULT -1 COMMENT 'Bounding rectangle (or ellipse bounding box) Y coordinate; -1 when not applicable to this annotation_type.',
  MODIFY COLUMN `rect_w` int(11) NOT NULL DEFAULT -1 COMMENT 'Bounding rectangle (or ellipse bounding box) width; -1 when not applicable to this annotation_type.',
  MODIFY COLUMN `rect_h` int(11) NOT NULL DEFAULT -1 COMMENT 'Bounding rectangle (or ellipse bounding box) height; -1 when not applicable to this annotation_type.',
  MODIFY COLUMN `window_x` int(11) NOT NULL DEFAULT -1 COMMENT 'Viewport X bound at the time the annotation was drawn, when recorded by the source system; -1 when not populated.',
  MODIFY COLUMN `window_y` int(11) NOT NULL DEFAULT -1 COMMENT 'Viewport Y bound at the time the annotation was drawn, when recorded by the source system; -1 when not populated.',
  MODIFY COLUMN `window_w` int(11) NOT NULL DEFAULT -1 COMMENT 'Viewport width at the time the annotation was drawn, when recorded by the source system; -1 when not populated.',
  MODIFY COLUMN `window_h` int(11) NOT NULL DEFAULT -1 COMMENT 'Viewport height at the time the annotation was drawn, when recorded by the source system; -1 when not populated.',
  MODIFY COLUMN `arrow_start_x` int(11) NOT NULL DEFAULT -1 COMMENT 'Start-point X for line-shaped annotations (arrow, measure); -1 when not applicable.',
  MODIFY COLUMN `arrow_start_y` int(11) NOT NULL DEFAULT -1 COMMENT 'Start-point Y for line-shaped annotations (arrow, measure); -1 when not applicable.',
  MODIFY COLUMN `arrow_end_x` int(11) NOT NULL DEFAULT -1 COMMENT 'End-point X for line-shaped annotations (arrow, measure); -1 when not applicable.',
  MODIFY COLUMN `arrow_end_y` int(11) NOT NULL DEFAULT -1 COMMENT 'End-point Y for line-shaped annotations (arrow, measure); -1 when not applicable.',
  MODIFY COLUMN `zoom` double NOT NULL COMMENT 'View-scale factor recorded at the time the annotation was drawn by the source system; whether coordinates need multiplying by this to reach full-resolution pixels is still being verified (see dih-slide-reconciler HANDOFF.md).',
  MODIFY COLUMN `focal_plane` int(10) unsigned NOT NULL DEFAULT 0 COMMENT 'Focal plane index the annotation was drawn on, for multi-focal-plane slides.',
  MODIFY COLUMN `current_frame` int(10) unsigned NOT NULL DEFAULT 0 COMMENT 'Frame/view index the annotation was drawn on, for multi-view slides.',
  MODIFY COLUMN `title` varchar(255) NOT NULL COMMENT 'Short heading/name for the annotation.',
  MODIFY COLUMN `description` varchar(255) NOT NULL COMMENT 'Longer free-text description, may include imported source comments.',
  MODIFY COLUMN `annotation_date` timestamp NULL DEFAULT NULL COMMENT 'When the annotation was originally authored in the source system.',
  MODIFY COLUMN `line_colour` varchar(255) NOT NULL COMMENT 'Display colour for the annotation outline, as recorded by the source system.',
  MODIFY COLUMN `drawing` longtext NULL DEFAULT NULL COMMENT 'Freehand/polygon shape data (HTML-escaped XML with a point list relative to rect_x/rect_y), only populated for annotation_type drawing/polygon.',
  MODIFY COLUMN `moveable` varchar(24) NOT NULL COMMENT 'Source system\'s movability flag for this annotation object.',
  MODIFY COLUMN `area` bigint(20) NOT NULL DEFAULT 0 COMMENT 'Measured area of the annotation, as recorded by the source system.',
  MODIFY COLUMN `filled` enum('true','false') NOT NULL DEFAULT 'false' COMMENT 'Whether the annotation shape is rendered filled (\'true\') or outline-only (\'false\').',
  MODIFY COLUMN `invisible` enum('true','false') NOT NULL DEFAULT 'false' COMMENT 'Whether the source system had this annotation marked hidden - real per-annotation data, not something to filter out by default (many slides have some or all annotations marked this way).',
  MODIFY COLUMN `tma_core` smallint(5) unsigned NULL DEFAULT NULL COMMENT 'Tissue microarray core index, for TMA slides.',
  MODIFY COLUMN `owner` int(11) NULL DEFAULT NULL COMMENT 'Numeric user id of the annotation\'s author in the source system (0 = system-recorded, e.g. scanned_region marking the scan bounds rather than a teaching annotation).',
  MODIFY COLUMN `source_annotation_id` int(11) NULL DEFAULT NULL COMMENT 'Original annotationId from the legacy dih database, for provenance/audit; NULL for annotations created directly in the app.',
  MODIFY COLUMN `created_date` timestamp NULL DEFAULT current_timestamp() COMMENT 'Row creation timestamp in this catalogue.',
  MODIFY COLUMN `updated_date` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp() COMMENT 'Row last-updated timestamp in this catalogue.';
ALTER TABLE `slide_corrections`
  MODIFY COLUMN `feedback_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  MODIFY COLUMN `slide_id` bigint(20) NOT NULL COMMENT 'Slide this feedback concerns.',
  MODIFY COLUMN `slide_filename` text NULL DEFAULT NULL COMMENT 'Slide\'s filename at submission time, kept for convenient display/export without a join.',
  MODIFY COLUMN `feedback_source` enum('metadata','slide_annotation','david_note') NOT NULL DEFAULT 'metadata' COMMENT 'Which part of the catalogue this feedback is about - \'metadata\' (organ/species/stain/etc.), \'slide_annotation\' (a reported annotation error), or \'david_note\' (an expert contributor note correction).',
  MODIFY COLUMN `feedback_type` varchar(100) NOT NULL DEFAULT 'general_comment' COMMENT 'For feedback_source=\'metadata\', which field is being corrected (organ, tissue, species, stain, description, notes, general_comment); for feedback_source=\'slide_annotation\', always \'annotation_review\'.',
  MODIFY COLUMN `source_annotation_id` bigint(20) NULL DEFAULT NULL COMMENT 'For feedback_source=\'slide_annotation\', the slide_annotations.annotation_id this report concerns.',
  MODIFY COLUMN `source_david_record_id` bigint(20) NULL DEFAULT NULL COMMENT 'For feedback_source=\'david_note\', the related david_jenkinson_curation.curation_id this correction concerns.',
  MODIFY COLUMN `current_value` text NULL DEFAULT NULL COMMENT 'The value/context being reported on at submission time.',
  MODIFY COLUMN `suggested_value` text NULL DEFAULT NULL COMMENT 'The submitter\'s suggested replacement value (or, for annotation reports, their verdict: \'correct\'/\'incorrect\').',
  MODIFY COLUMN `feedback_text` text NOT NULL COMMENT 'Free-text explanation/reasoning from the submitter.',
  MODIFY COLUMN `submitter_username` varchar(191) NOT NULL COMMENT 'Username of the user who submitted this feedback, captured at submission time.',
  MODIFY COLUMN `submitter_email` varchar(255) NULL DEFAULT NULL COMMENT 'Email of the submitting user, captured at submission time.',
  MODIFY COLUMN `submitter_display_name` varchar(255) NULL DEFAULT NULL COMMENT 'Display name of the submitting user, captured at submission time.',
  MODIFY COLUMN `submitter_role` varchar(50) NULL DEFAULT NULL COMMENT 'Role of the submitting user, captured at submission time (a later role change doesn\'t rewrite this).',
  MODIFY COLUMN `status` enum('new','under_review','accepted','rejected','resolved') NOT NULL DEFAULT 'new' COMMENT 'Review workflow state - new, under_review, accepted, rejected, or resolved.',
  MODIFY COLUMN `admin_notes` text NULL DEFAULT NULL COMMENT 'Reviewer\'s notes, added when changing status.',
  MODIFY COLUMN `reviewed_by_username` varchar(191) NULL DEFAULT NULL COMMENT 'Username of whoever last changed this correction\'s status.',
  MODIFY COLUMN `reviewed_at` datetime NULL DEFAULT NULL COMMENT 'When the status was last changed.',
  MODIFY COLUMN `remote_addr` varchar(100) NULL DEFAULT NULL COMMENT 'Submitter\'s IP address, captured for abuse/audit purposes.',
  MODIFY COLUMN `user_agent` varchar(500) NULL DEFAULT NULL COMMENT 'Submitter\'s browser user-agent, captured for abuse/audit purposes.',
  MODIFY COLUMN `legacy_metadata_feedback_id` bigint(20) NULL DEFAULT NULL COMMENT 'Reference to a pre-migration feedback record, for rows imported from an earlier version of this feature.',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT 'Row creation timestamp.',
  MODIFY COLUMN `updated_at` datetime NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Row last-updated timestamp.';
ALTER TABLE `slide_correction_actions`
  MODIFY COLUMN `action_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  MODIFY COLUMN `feedback_id` bigint(20) NOT NULL COMMENT 'The slide_corrections row this action was taken against.',
  MODIFY COLUMN `slide_id` bigint(20) NOT NULL COMMENT 'Slide the correction concerns, denormalised for convenient querying.',
  MODIFY COLUMN `action_type` enum('status_update','metadata_update') NOT NULL COMMENT 'Kind of action performed - status_update (correction\'s status changed) or metadata_update (a metadata field was actually applied to the slide).',
  MODIFY COLUMN `field_name` varchar(100) NULL DEFAULT NULL COMMENT 'For metadata_update actions, which slide_metadata/slide_tissue_annotations field was changed; for status_update actions, always \'status\'.',
  MODIFY COLUMN `old_value` text NULL DEFAULT NULL COMMENT 'The value before this action.',
  MODIFY COLUMN `new_value` text NULL DEFAULT NULL COMMENT 'The value after this action.',
  MODIFY COLUMN `action_notes` text NULL DEFAULT NULL COMMENT 'Free-text notes attached to this specific action.',
  MODIFY COLUMN `performed_by_username` varchar(191) NOT NULL COMMENT 'Username of the admin/reviewer who performed this action.',
  MODIFY COLUMN `performed_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT 'When this action was performed.';
ALTER TABLE `users`
  MODIFY COLUMN `user_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  MODIFY COLUMN `username` varchar(255) NOT NULL COMMENT 'Unique login identifier.',
  MODIFY COLUMN `email` varchar(255) NOT NULL COMMENT 'Unique email address, used for notifications and password reset.',
  MODIFY COLUMN `full_name` varchar(255) NOT NULL COMMENT 'Display name.',
  MODIFY COLUMN `institution` varchar(255) NULL DEFAULT NULL COMMENT 'Self-reported institution/affiliation.',
  MODIFY COLUMN `guid` varchar(64) NULL DEFAULT NULL COMMENT 'External identity provider GUID, for LDAP-authenticated accounts.',
  MODIFY COLUMN `role` enum('user','admin','system_admin','reviewer','expert') NOT NULL DEFAULT 'user' COMMENT 'Access level - user, admin, system_admin (full access, DB-assignable only), reviewer (corrections.view/review permissions), or expert (expert_notes.write permission). See role_permissions.',
  MODIFY COLUMN `authentication_method` enum('LOCAL','LDAP') NOT NULL DEFAULT 'LOCAL' COMMENT 'Whether this account logs in with a local password (LOCAL) or an institutional LDAP account (LDAP).',
  MODIFY COLUMN `account_status` enum('PENDING_ACTIVATION','ACTIVE','DISABLED') NOT NULL DEFAULT 'PENDING_ACTIVATION' COMMENT 'PENDING_ACTIVATION (approved but not yet activated), ACTIVE, or DISABLED.',
  MODIFY COLUMN `contributions_count` int(11) NOT NULL DEFAULT 0 COMMENT 'Total number of feedback/correction submissions made by this user.',
  MODIFY COLUMN `contributions_accepted_count` int(11) NOT NULL DEFAULT 0 COMMENT 'Number of this user\'s submissions that were acted on (resolved).',
  MODIFY COLUMN `password_hash` text NULL DEFAULT NULL COMMENT 'Argon2 hash of the account\'s local password; NULL for LDAP-authenticated accounts.',
  MODIFY COLUMN `approved_by` varchar(100) NULL DEFAULT NULL COMMENT 'Username of the admin who approved this account\'s access request.',
  MODIFY COLUMN `approved_at` timestamp NULL DEFAULT NULL COMMENT 'When this account\'s access request was approved.',
  MODIFY COLUMN `created_at` timestamp NULL DEFAULT current_timestamp() COMMENT 'When this user record was created.',
  MODIFY COLUMN `last_login_at` datetime NULL DEFAULT NULL COMMENT 'Timestamp of this user\'s most recent successful login.';
ALTER TABLE `role_permissions`
  MODIFY COLUMN `role` varchar(50) NOT NULL COMMENT 'Role name this row grants a permission to (users.role).',
  MODIFY COLUMN `permission_key` varchar(100) NOT NULL COMMENT 'Capability being granted, e.g. corrections.view, corrections.review, expert_notes.write - checked by app.permissions.require_permission().';
ALTER TABLE `slide_expert_notes`
  MODIFY COLUMN `note_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  MODIFY COLUMN `slide_id` bigint(20) NOT NULL COMMENT 'Slide this note is attached to.',
  MODIFY COLUMN `author_username` varchar(191) NOT NULL COMMENT 'Username of the expert who wrote this note.',
  MODIFY COLUMN `author_display_name` varchar(255) NULL DEFAULT NULL COMMENT 'Display name of the note\'s author, captured at write time for convenient display.',
  MODIFY COLUMN `note_title` varchar(255) NULL DEFAULT NULL COMMENT 'Optional short title for the note.',
  MODIFY COLUMN `note_text` text NOT NULL COMMENT 'The note\'s content.',
  MODIFY COLUMN `created_at` datetime NULL DEFAULT current_timestamp() COMMENT 'Row creation timestamp.',
  MODIFY COLUMN `updated_at` datetime NULL DEFAULT current_timestamp() ON UPDATE current_timestamp() COMMENT 'Row last-updated timestamp.';
ALTER TABLE `access_requests`
  MODIFY COLUMN `request_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  MODIFY COLUMN `full_name` varchar(255) NOT NULL COMMENT 'Requester\'s full name.',
  MODIFY COLUMN `email` varchar(255) NOT NULL COMMENT 'Requester\'s email address.',
  MODIFY COLUMN `institution` varchar(255) NOT NULL COMMENT 'Requester\'s self-reported institution/affiliation.',
  MODIFY COLUMN `guid` varchar(64) NULL DEFAULT NULL COMMENT 'External identity provider GUID, if applying via LDAP.',
  MODIFY COLUMN `authentication_method` enum('LOCAL','LDAP') NOT NULL DEFAULT 'LOCAL' COMMENT 'Whether the resulting account should authenticate locally (LOCAL) or via LDAP.',
  MODIFY COLUMN `request_reason` text NOT NULL COMMENT 'Requester\'s free-text reason for wanting access.',
  MODIFY COLUMN `status` enum('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING, APPROVED, or REJECTED.',
  MODIFY COLUMN `submitted_at` timestamp NULL DEFAULT current_timestamp() COMMENT 'When the request was submitted.',
  MODIFY COLUMN `reviewed_at` timestamp NULL DEFAULT NULL COMMENT 'When an admin reviewed this request.',
  MODIFY COLUMN `reviewed_by` varchar(100) NULL DEFAULT NULL COMMENT 'Username of the admin who reviewed this request.',
  MODIFY COLUMN `review_notes` text NULL DEFAULT NULL COMMENT 'Admin\'s free-text notes on the decision.';
ALTER TABLE `access_request_blocked_attempts`
  MODIFY COLUMN `attempt_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  MODIFY COLUMN `attempted_email` varchar(255) NOT NULL COMMENT 'Email address used in the blocked attempt.',
  MODIFY COLUMN `attempted_full_name` varchar(255) NULL DEFAULT NULL COMMENT 'Full name given in the blocked attempt.',
  MODIFY COLUMN `reason` enum('email_already_registered','duplicate_pending_request') NOT NULL COMMENT 'Why the attempt was blocked automatically - email_already_registered or duplicate_pending_request.',
  MODIFY COLUMN `remote_addr` varchar(100) NULL DEFAULT NULL COMMENT 'IP address the attempt came from.',
  MODIFY COLUMN `user_agent` varchar(500) NULL DEFAULT NULL COMMENT 'Browser user-agent of the attempt.',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT 'When the blocked attempt occurred.';
ALTER TABLE `annotation_contributors`
  MODIFY COLUMN `contributor_id` int(11) NOT NULL COMMENT 'Primary key (matches the source system\'s own user/owner id where applicable).',
  MODIFY COLUMN `first_name` varchar(255) NULL DEFAULT NULL COMMENT 'Contributor\'s first name.',
  MODIFY COLUMN `surname` varchar(255) NULL DEFAULT NULL COMMENT 'Contributor\'s surname.',
  MODIFY COLUMN `source_system` varchar(100) NULL DEFAULT NULL COMMENT 'Which legacy/source system this contributor record came from (e.g. dih).',
  MODIFY COLUMN `notes` text NULL DEFAULT NULL COMMENT 'Free-text notes.';
ALTER TABLE `david_record_slide_links`
  MODIFY COLUMN `david_record_id` bigint(20) NOT NULL COMMENT 'The david_jenkinson_curation.curation_id being linked.',
  MODIFY COLUMN `slide_id` bigint(20) NOT NULL COMMENT 'The slides.slide_id being linked.',
  MODIFY COLUMN `confidence_score` decimal(5,2) NULL DEFAULT NULL COMMENT 'Confidence in this specific link.',
  MODIFY COLUMN `link_method` varchar(100) NULL DEFAULT NULL COMMENT 'How this link was derived (e.g. filename match, manual review).',
  MODIFY COLUMN `notes` text NULL DEFAULT NULL COMMENT 'Free-text notes on this link.';
ALTER TABLE `password_reset_log`
  MODIFY COLUMN `log_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  MODIFY COLUMN `user_id` int(11) NULL DEFAULT NULL COMMENT 'The users.user_id this attempt was for, when the email matched an account.',
  MODIFY COLUMN `email_provided` varchar(255) NOT NULL COMMENT 'Email address entered in the reset request.',
  MODIFY COLUMN `event_type` enum('requested','completed','invalid_email','inactive_account') NOT NULL COMMENT 'requested (reset email sent), completed (password actually changed), invalid_email (no matching account), or inactive_account (account not ACTIVE).',
  MODIFY COLUMN `remote_addr` varchar(100) NULL DEFAULT NULL COMMENT 'IP address the request came from.',
  MODIFY COLUMN `user_agent` varchar(500) NULL DEFAULT NULL COMMENT 'Browser user-agent of the request.',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT 'When this event occurred.';
ALTER TABLE `password_reset_tokens`
  MODIFY COLUMN `token_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  MODIFY COLUMN `user_id` int(11) NOT NULL COMMENT 'The users.user_id this token was issued for.',
  MODIFY COLUMN `reset_token` char(36) NOT NULL COMMENT 'The single-use token value emailed to the user.',
  MODIFY COLUMN `created_at` timestamp NULL DEFAULT current_timestamp() COMMENT 'When the token was issued.',
  MODIFY COLUMN `expires_at` timestamp NULL DEFAULT NULL COMMENT 'When the token stops being valid.',
  MODIFY COLUMN `used_at` timestamp NULL DEFAULT NULL COMMENT 'When the token was redeemed; NULL if not yet used.';
ALTER TABLE `user_activation_tokens`
  MODIFY COLUMN `token_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  MODIFY COLUMN `user_id` int(11) NOT NULL COMMENT 'The users.user_id this token was issued for.',
  MODIFY COLUMN `activation_token` char(36) NOT NULL COMMENT 'The single-use token value emailed to the user.',
  MODIFY COLUMN `created_at` timestamp NULL DEFAULT current_timestamp() COMMENT 'When the token was issued.',
  MODIFY COLUMN `expires_at` timestamp NULL DEFAULT NULL COMMENT 'When the token stops being valid.',
  MODIFY COLUMN `used_at` timestamp NULL DEFAULT NULL COMMENT 'When the token was redeemed; NULL if not yet used.';
ALTER TABLE `site_feedback`
  MODIFY COLUMN `feedback_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  MODIFY COLUMN `feedback_text` text NOT NULL COMMENT 'The submitted feedback content.',
  MODIFY COLUMN `page_url` varchar(500) NULL DEFAULT NULL COMMENT 'URL of the page the feedback was submitted from.',
  MODIFY COLUMN `submitter_username` varchar(191) NOT NULL COMMENT 'Username of the user who submitted this feedback, captured at submission time.',
  MODIFY COLUMN `submitter_email` varchar(255) NULL DEFAULT NULL COMMENT 'Email of the submitting user, captured at submission time.',
  MODIFY COLUMN `submitter_display_name` varchar(255) NULL DEFAULT NULL COMMENT 'Display name of the submitting user, captured at submission time.',
  MODIFY COLUMN `submitter_role` varchar(50) NULL DEFAULT NULL COMMENT 'Role of the submitting user, captured at submission time.',
  MODIFY COLUMN `status` enum('new','under_review','accepted','rejected','resolved') NOT NULL DEFAULT 'new' COMMENT 'Review workflow state - new, under_review, accepted, rejected, or resolved.',
  MODIFY COLUMN `admin_notes` text NULL DEFAULT NULL COMMENT 'Reviewer\'s notes.',
  MODIFY COLUMN `reviewed_by_username` varchar(191) NULL DEFAULT NULL COMMENT 'Username of whoever last reviewed this feedback.',
  MODIFY COLUMN `reviewed_at` datetime NULL DEFAULT NULL COMMENT 'When it was last reviewed.',
  MODIFY COLUMN `remote_addr` varchar(100) NULL DEFAULT NULL COMMENT 'Submitter\'s IP address, captured for abuse/audit purposes.',
  MODIFY COLUMN `user_agent` varchar(500) NULL DEFAULT NULL COMMENT 'Submitter\'s browser user-agent, captured for abuse/audit purposes.',
  MODIFY COLUMN `created_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT 'Row creation timestamp.',
  MODIFY COLUMN `updated_at` datetime NULL DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Row last-updated timestamp.';
ALTER TABLE `system_settings`
  MODIFY COLUMN `setting_name` varchar(100) NOT NULL COMMENT 'Primary key - the setting\'s identifier.',
  MODIFY COLUMN `setting_value` text NOT NULL COMMENT 'The setting\'s current value, stored as text.',
  MODIFY COLUMN `updated_by` varchar(100) NULL DEFAULT NULL COMMENT 'Username of the admin who last changed this setting.',
  MODIFY COLUMN `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp() COMMENT 'When this setting was last changed.';
ALTER TABLE `david_slide_match_stage`
  MODIFY COLUMN `curation_id` bigint(20) NOT NULL COMMENT 'The david_jenkinson_curation.curation_id being considered.',
  MODIFY COLUMN `candidate_slide_id` bigint(20) NOT NULL COMMENT 'The slides.slide_id being considered as a match.',
  MODIFY COLUMN `david_slide_reference` varchar(255) NULL DEFAULT NULL COMMENT 'Slide reference/label as recorded in the David Jenkinson source material.',
  MODIFY COLUMN `david_organ` varchar(255) NULL DEFAULT NULL COMMENT 'Organ as recorded in the David Jenkinson source material.',
  MODIFY COLUMN `david_species` varchar(255) NULL DEFAULT NULL COMMENT 'Species as recorded in the David Jenkinson source material.',
  MODIFY COLUMN `david_stain` varchar(255) NULL DEFAULT NULL COMMENT 'Stain as recorded in the David Jenkinson source material.',
  MODIFY COLUMN `david_tissue` varchar(255) NULL DEFAULT NULL COMMENT 'Tissue as recorded in the David Jenkinson source material.',
  MODIFY COLUMN `catalogue_organ` varchar(255) NULL DEFAULT NULL COMMENT 'Organ as currently recorded in the catalogue for the candidate slide.',
  MODIFY COLUMN `catalogue_species` varchar(255) NULL DEFAULT NULL COMMENT 'Species as currently recorded in the catalogue for the candidate slide.',
  MODIFY COLUMN `catalogue_stain` varchar(255) NULL DEFAULT NULL COMMENT 'Stain as currently recorded in the catalogue for the candidate slide.',
  MODIFY COLUMN `catalogue_tissue` varchar(255) NULL DEFAULT NULL COMMENT 'Tissue as currently recorded in the catalogue for the candidate slide.',
  MODIFY COLUMN `match_method` varchar(100) NOT NULL COMMENT 'How this candidate pairing was proposed (e.g. filename match, manual review).',
  MODIFY COLUMN `identity_confidence` decimal(5,2) NULL DEFAULT NULL COMMENT 'Overall confidence score for this candidate match.',
  MODIFY COLUMN `tissue_match` tinyint(1) NULL DEFAULT 0 COMMENT 'Whether the David Jenkinson and catalogue tissue values agree (1) or not (0).',
  MODIFY COLUMN `stain_match` tinyint(1) NULL DEFAULT 0 COMMENT 'Whether the David Jenkinson and catalogue stain values agree (1) or not (0).',
  MODIFY COLUMN `organ_match` tinyint(1) NULL DEFAULT 0 COMMENT 'Whether the David Jenkinson and catalogue organ values agree (1) or not (0).',
  MODIFY COLUMN `species_match` tinyint(1) NULL DEFAULT 0 COMMENT 'Whether the David Jenkinson and catalogue species values agree (1) or not (0).',
  MODIFY COLUMN `review_status` varchar(50) NULL DEFAULT 'PENDING' COMMENT 'Curation status of this candidate match, e.g. PENDING, APPROVED, REJECTED.',
  MODIFY COLUMN `match_notes` text NULL DEFAULT NULL COMMENT 'Free-text reviewer notes on this candidate match.',
  MODIFY COLUMN `created_at` timestamp NULL DEFAULT current_timestamp() COMMENT 'When this candidate match was staged.';
