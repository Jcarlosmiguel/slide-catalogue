-- Base schema for the catalogue database, extracted from a production
-- schema dump with all data stripped - CREATE TABLE only. Excludes
-- role_permissions, slide_expert_notes, legacy_curation_edit_history (created
-- by migration 0001/0003) and schema_migrations (managed by
-- run_migrations.sh itself).
--
-- Numbered like any other migration, so run_migrations.sh picks it up and
-- applies it first automatically on a fresh database - no separate manual
-- step needed. See run_migrations.sh for usage.

-- Table creation order below isn't dependency-sorted (alphabetical from the
-- source dump), so foreign keys must be allowed to reference not-yet-created
-- tables during this one script; restored to normal immediately after.
SET FOREIGN_KEY_CHECKS=0;

DROP TABLE IF EXISTS `access_request_blocked_attempts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `access_request_blocked_attempts` (
  `attempt_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  `attempted_email` varchar(255) NOT NULL COMMENT 'Email address used in the blocked attempt.',
  `attempted_full_name` varchar(255) DEFAULT NULL COMMENT 'Full name given in the blocked attempt.',
  `reason` enum('email_already_registered','duplicate_pending_request') NOT NULL COMMENT 'Why the attempt was blocked automatically - email_already_registered or duplicate_pending_request.',
  `remote_addr` varchar(100) DEFAULT NULL COMMENT 'IP address the attempt came from.',
  `user_agent` varchar(500) DEFAULT NULL COMMENT 'Browser user-agent of the attempt.',
  `created_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT 'When the blocked attempt occurred.',
  PRIMARY KEY (`attempt_id`),
  KEY `idx_attempted_email` (`attempted_email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Log of access requests rejected automatically before reaching the review queue (e.g. duplicate email already registered), kept for abuse monitoring.';

DROP TABLE IF EXISTS `access_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `access_requests` (
  `request_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  `full_name` varchar(255) NOT NULL COMMENT 'Requester''s full name.',
  `email` varchar(255) NOT NULL COMMENT 'Requester''s email address.',
  `institution` varchar(255) NOT NULL COMMENT 'Requester''s self-reported institution/affiliation.',
  `guid` varchar(64) DEFAULT NULL COMMENT 'External identity provider GUID, if applying via LDAP.',
  `authentication_method` enum('LOCAL','LDAP') NOT NULL DEFAULT 'LOCAL' COMMENT 'Whether the resulting account should authenticate locally (LOCAL) or via LDAP.',
  `request_reason` text NOT NULL COMMENT 'Requester''s free-text reason for wanting access.',
  `status` enum('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING, APPROVED, or REJECTED.',
  `submitted_at` timestamp NULL DEFAULT current_timestamp() COMMENT 'When the request was submitted.',
  `reviewed_at` timestamp NULL DEFAULT NULL COMMENT 'When an admin reviewed this request.',
  `reviewed_by` varchar(100) DEFAULT NULL COMMENT 'Username of the admin who reviewed this request.',
  `review_notes` text DEFAULT NULL COMMENT 'Admin''s free-text notes on the decision.',
  PRIMARY KEY (`request_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Self-service requests for catalogue access, reviewed by an admin before a user account is created.';

DROP TABLE IF EXISTS `annotation_contributors`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `annotation_contributors` (
  `contributor_id` int(11) NOT NULL COMMENT 'Primary key (matches the source system''s own user/owner id where applicable).',
  `first_name` varchar(255) DEFAULT NULL COMMENT 'Contributor''s first name.',
  `surname` varchar(255) DEFAULT NULL COMMENT 'Contributor''s surname.',
  `source_system` varchar(100) DEFAULT NULL COMMENT 'Which legacy/source system this contributor record came from (e.g. dih).',
  `notes` text DEFAULT NULL COMMENT 'Free-text notes.',
  PRIMARY KEY (`contributor_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Reference list of individuals credited as annotation contributors/authors in imported source data, for display and attribution.';

DROP TABLE IF EXISTS `legacy_curation`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `legacy_curation` (
  `curation_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  `source_file` varchar(500) NOT NULL COMMENT 'Original source document from the legacy contributor archive.',
  `source_authorship` varchar(255) NOT NULL DEFAULT 'legacy contributor' COMMENT 'Original authorship attribution for the source material.',
  `slide_reference` varchar(255) DEFAULT NULL COMMENT 'Slide identifier, slide number or textual slide reference extracted from the source document.',
  `matched_slide_id` bigint(20) DEFAULT NULL COMMENT 'Catalogue slide matched through automated or manual reconciliation. NULL indicates no confirmed match.',
  `record_type` varchar(100) DEFAULT NULL COMMENT 'Classification of extracted content such as keyword, annotation, teaching note, specimen observation or narrative text.',
  `keyword_text` longtext DEFAULT NULL COMMENT 'Keywords or structured annotation terms extracted from the source document.',
  `note_text` longtext DEFAULT NULL COMMENT 'Narrative curation content, teaching notes, specimen observations or annotation text extracted from the source document.',
  `original_text` longtext DEFAULT NULL COMMENT 'Original extracted text preserved for provenance and future reprocessing.',
  `match_confidence` decimal(5,2) DEFAULT NULL COMMENT 'Confidence score assigned to any slide match.',
  `source_verified` tinyint(1) NOT NULL DEFAULT 0 COMMENT 'Indicates whether extracted content has been reviewed against the original source document.',
  `imported_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Timestamp when the record was imported into the curation corpus.',
  `organ` varchar(255) DEFAULT NULL COMMENT 'Organ or tissue associated with the extracted record.',
  `species` varchar(255) DEFAULT NULL COMMENT 'Species associated with the extracted record where identified from the source material.',
  `stain` varchar(255) DEFAULT NULL COMMENT 'Histological stain or preparation method associated with the source material.',
  `slide_name` varchar(255) DEFAULT NULL COMMENT 'Legacy contributor local catalogue designation, e.g. Kidney 1, Trachea 4, Pancreas 8.',
  `annotation_title` varchar(500) DEFAULT NULL COMMENT 'Title or feature heading associated with the annotation text.',
  `source_archive` varchar(255) DEFAULT NULL COMMENT 'Archive grouping from which the source document originated within the legacy contributor curation archive.',
  PRIMARY KEY (`curation_id`),
  KEY `idx_source_file` (`source_file`),
  KEY `idx_slide_reference` (`slide_reference`),
  KEY `idx_matched_slide_id` (`matched_slide_id`),
  KEY `idx_record_type` (`record_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Curated legacy contributor annotation records and note text linked to slides through slide_legacy_curation_links.';

DROP TABLE IF EXISTS `legacy_curation_slide_links`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `legacy_curation_slide_links` (
  `legacy_curation_id` bigint(20) NOT NULL COMMENT 'The legacy_curation.curation_id being linked.',
  `slide_id` bigint(20) NOT NULL COMMENT 'The slides.slide_id being linked.',
  `confidence_score` decimal(5,2) DEFAULT NULL COMMENT 'Confidence in this specific link.',
  `link_method` varchar(100) DEFAULT NULL COMMENT 'How this link was derived (e.g. filename match, manual review).',
  `notes` text DEFAULT NULL COMMENT 'Free-text notes on this link.',
  PRIMARY KEY (`legacy_curation_id`,`slide_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Reconciliation candidates/links between legacy_curation records and catalogue slides - a broader or earlier-stage table than the confirmed slide_legacy_curation_links.';

DROP TABLE IF EXISTS `legacy_curation_match_stage`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `legacy_curation_match_stage` (
  `curation_id` bigint(20) NOT NULL COMMENT 'The legacy_curation.curation_id being considered.',
  `candidate_slide_id` bigint(20) NOT NULL COMMENT 'The slides.slide_id being considered as a match.',
  `legacy_slide_reference` varchar(255) DEFAULT NULL COMMENT 'Slide reference/label as recorded in the legacy contributor source material.',
  `legacy_organ` varchar(255) DEFAULT NULL COMMENT 'Organ as recorded in the legacy contributor source material.',
  `legacy_species` varchar(255) DEFAULT NULL COMMENT 'Species as recorded in the legacy contributor source material.',
  `legacy_stain` varchar(255) DEFAULT NULL COMMENT 'Stain as recorded in the legacy contributor source material.',
  `legacy_tissue` varchar(255) DEFAULT NULL COMMENT 'Tissue as recorded in the legacy contributor source material.',
  `catalogue_organ` varchar(255) DEFAULT NULL COMMENT 'Organ as currently recorded in the catalogue for the candidate slide.',
  `catalogue_species` varchar(255) DEFAULT NULL COMMENT 'Species as currently recorded in the catalogue for the candidate slide.',
  `catalogue_stain` varchar(255) DEFAULT NULL COMMENT 'Stain as currently recorded in the catalogue for the candidate slide.',
  `catalogue_tissue` varchar(255) DEFAULT NULL COMMENT 'Tissue as currently recorded in the catalogue for the candidate slide.',
  `match_method` varchar(100) NOT NULL COMMENT 'How this candidate pairing was proposed (e.g. filename match, manual review).',
  `identity_confidence` decimal(5,2) DEFAULT NULL COMMENT 'Overall confidence score for this candidate match.',
  `tissue_match` tinyint(1) DEFAULT 0 COMMENT 'Whether the legacy contributor and catalogue tissue values agree (1) or not (0).',
  `stain_match` tinyint(1) DEFAULT 0 COMMENT 'Whether the legacy contributor and catalogue stain values agree (1) or not (0).',
  `organ_match` tinyint(1) DEFAULT 0 COMMENT 'Whether the legacy contributor and catalogue organ values agree (1) or not (0).',
  `species_match` tinyint(1) DEFAULT 0 COMMENT 'Whether the legacy contributor and catalogue species values agree (1) or not (0).',
  `review_status` varchar(50) DEFAULT 'PENDING' COMMENT 'Curation status of this candidate match, e.g. PENDING, APPROVED, REJECTED.',
  `match_notes` text DEFAULT NULL COMMENT 'Free-text reviewer notes on this candidate match.',
  `created_at` timestamp NULL DEFAULT current_timestamp() COMMENT 'When this candidate match was staged.',
  PRIMARY KEY (`curation_id`,`candidate_slide_id`,`match_method`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Staging table for many-to-many matching of legacy contributor records to slide_id values. Only approved rows should be inserted into slide_legacy_curation_links.';

DROP TABLE IF EXISTS `duplicate_slide_mapping`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `duplicate_slide_mapping` (
  `duplicate_slide_id` bigint(20) NOT NULL COMMENT 'The slides.slide_id identified as a duplicate.',
  `canonical_slide_id` bigint(20) NOT NULL COMMENT 'The slides.slide_id this duplicate should be treated as equivalent to.',
  `duplicate_crawler_id` bigint(20) DEFAULT NULL COMMENT 'Crawler-assigned identifier for the duplicate file, kept for provenance.',
  `reason` varchar(255) DEFAULT NULL COMMENT 'Why this slide was flagged as a duplicate.',
  `evidence` text DEFAULT NULL COMMENT 'Free-text supporting evidence for the duplicate determination.',
  `created_date` timestamp NULL DEFAULT current_timestamp() COMMENT 'When this mapping was recorded.',
  PRIMARY KEY (`duplicate_slide_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Temporary curation table for suspected or confirmed duplicate slide mappings.';

DROP TABLE IF EXISTS `organ_dictionary`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `organ_dictionary` (
  `organ_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  `organ_name` varchar(255) NOT NULL COMMENT 'Raw/original organ name as it appears in source data before normalisation.',
  `organ_system` varchar(255) DEFAULT NULL COMMENT 'Broader body system this organ belongs to (e.g. Cardiovascular, Respiratory).',
  `active` tinyint(1) DEFAULT 1 COMMENT 'Whether this dictionary entry is currently in active use (0 = retired/superseded).',
  `notes` text DEFAULT NULL COMMENT 'Free-text curator notes.',
  `canonical_organ` varchar(255) DEFAULT NULL COMMENT 'Preferred canonical organ or anatomical structure name',
  `organ_group` varchar(255) DEFAULT NULL COMMENT 'Broad anatomical grouping used for search and reconciliation',
  `normalisation_status` varchar(50) DEFAULT NULL COMMENT 'Status of dictionary normalisation, e.g. NORMALISED, REVIEW, EXCLUDED',
  `also_known_as` text DEFAULT NULL COMMENT 'Comma-separated aliases, abbreviations, spelling variants, or legacy labels',
  `review_status` varchar(50) DEFAULT NULL COMMENT 'Dictionary curation status, e.g. APPROVED, PENDING, REVIEW',
  `confidence` varchar(20) DEFAULT NULL COMMENT 'Confidence in the canonical mapping, e.g. HIGH, MEDIUM, LOW',
  PRIMARY KEY (`organ_id`),
  UNIQUE KEY `uq_organ_name` (`organ_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Permanent dictionary of canonical anatomical organs and anatomical structures used to normalise slide_metadata.organ.';

DROP TABLE IF EXISTS `organ_tissue_dictionary`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `organ_tissue_dictionary` (
  `organ_id` int(11) NOT NULL COMMENT 'Organ side of the relationship (organ_dictionary.organ_id).',
  `tissue_id` int(11) NOT NULL COMMENT 'Tissue side of the relationship (tissue_dictionary.tissue_id).',
  `notes` text DEFAULT NULL COMMENT 'Free-text curator notes.',
  `relationship_type` varchar(100) DEFAULT NULL COMMENT 'Nature of organ-tissue relationship, e.g. CONTAINS, REGION_OF, ASSOCIATED_WITH',
  `review_status` varchar(50) DEFAULT NULL COMMENT 'Curation status of this organ-tissue relationship',
  `confidence` varchar(20) DEFAULT NULL COMMENT 'Confidence in this relationship, e.g. HIGH, MEDIUM, LOW',
  PRIMARY KEY (`organ_id`,`tissue_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Permanent bridge table describing curated relationships between canonical organs and canonical tissues.';

DROP TABLE IF EXISTS `password_reset_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `password_reset_log` (
  `log_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  `user_id` int(11) DEFAULT NULL COMMENT 'The users.user_id this attempt was for, when the email matched an account.',
  `email_provided` varchar(255) NOT NULL COMMENT 'Email address entered in the reset request.',
  `event_type` enum('requested','completed','invalid_email','inactive_account') NOT NULL COMMENT 'requested (reset email sent), completed (password actually changed), invalid_email (no matching account), or inactive_account (account not ACTIVE).',
  `remote_addr` varchar(100) DEFAULT NULL COMMENT 'IP address the request came from.',
  `user_agent` varchar(500) DEFAULT NULL COMMENT 'Browser user-agent of the request.',
  `created_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT 'When this event occurred.',
  PRIMARY KEY (`log_id`),
  KEY `idx_email_provided` (`email_provided`),
  KEY `fk_password_reset_log_user` (`user_id`),
  CONSTRAINT `fk_password_reset_log_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Audit log of password-reset attempts, successful or not, for abuse monitoring and support troubleshooting.';

DROP TABLE IF EXISTS `password_reset_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `password_reset_tokens` (
  `token_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  `user_id` int(11) NOT NULL COMMENT 'The users.user_id this token was issued for.',
  `reset_token` char(36) NOT NULL COMMENT 'The single-use token value emailed to the user.',
  `created_at` timestamp NULL DEFAULT current_timestamp() COMMENT 'When the token was issued.',
  `expires_at` timestamp NULL DEFAULT NULL COMMENT 'When the token stops being valid.',
  `used_at` timestamp NULL DEFAULT NULL COMMENT 'When the token was redeemed; NULL if not yet used.',
  PRIMARY KEY (`token_id`),
  UNIQUE KEY `reset_token` (`reset_token`),
  KEY `fk_password_reset_user` (`user_id`),
  CONSTRAINT `fk_password_reset_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Single-use, time-limited tokens issued for the forgot-password flow.';

DROP TABLE IF EXISTS `site_feedback`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `site_feedback` (
  `feedback_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  `feedback_text` text NOT NULL COMMENT 'The submitted feedback content.',
  `page_url` varchar(500) DEFAULT NULL COMMENT 'URL of the page the feedback was submitted from.',
  `submitter_username` varchar(191) NOT NULL COMMENT 'Username of the user who submitted this feedback, captured at submission time.',
  `submitter_email` varchar(255) DEFAULT NULL COMMENT 'Email of the submitting user, captured at submission time.',
  `submitter_display_name` varchar(255) DEFAULT NULL COMMENT 'Display name of the submitting user, captured at submission time.',
  `submitter_role` varchar(50) DEFAULT NULL COMMENT 'Role of the submitting user, captured at submission time.',
  `status` enum('new','under_review','accepted','rejected','resolved') NOT NULL DEFAULT 'new' COMMENT 'Review workflow state - new, under_review, accepted, rejected, or resolved.',
  `admin_notes` text DEFAULT NULL COMMENT 'Reviewer''s notes.',
  `reviewed_by_username` varchar(191) DEFAULT NULL COMMENT 'Username of whoever last reviewed this feedback.',
  `reviewed_at` datetime DEFAULT NULL COMMENT 'When it was last reviewed.',
  `remote_addr` varchar(100) DEFAULT NULL COMMENT 'Submitter''s IP address, captured for abuse/audit purposes.',
  `user_agent` varchar(500) DEFAULT NULL COMMENT 'Submitter''s browser user-agent, captured for abuse/audit purposes.',
  `created_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT 'Row creation timestamp.',
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Row last-updated timestamp.',
  PRIMARY KEY (`feedback_id`),
  KEY `idx_status` (`status`),
  KEY `idx_submitter` (`submitter_username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='General free-text feedback about the catalogue site/UX, not tied to a specific slide or correction - distinct from slide_corrections.';

DROP TABLE IF EXISTS `slide_annotations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slide_annotations` (
  `annotation_id` bigint(20) NOT NULL COMMENT 'Primary key; reuses dih''s own annotationId for imported rows so it''s a stable global identifier.',
  `slide_id` bigint(20) NOT NULL COMMENT 'Slide this annotation belongs to (slides.slide_id).',
  `annotation_type` varchar(128) NOT NULL COMMENT 'Shape/kind of annotation (e.g. rectangle, ellipse, arrow, measure, pin, drawing, polygon, scanned_region).',
  `rect_x` int(11) NOT NULL DEFAULT -1 COMMENT 'Bounding rectangle (or ellipse bounding box) X coordinate; -1 when not applicable to this annotation_type.',
  `rect_y` int(11) NOT NULL DEFAULT -1 COMMENT 'Bounding rectangle (or ellipse bounding box) Y coordinate; -1 when not applicable to this annotation_type.',
  `rect_w` int(11) NOT NULL DEFAULT -1 COMMENT 'Bounding rectangle (or ellipse bounding box) width; -1 when not applicable to this annotation_type.',
  `rect_h` int(11) NOT NULL DEFAULT -1 COMMENT 'Bounding rectangle (or ellipse bounding box) height; -1 when not applicable to this annotation_type.',
  `window_x` int(11) NOT NULL DEFAULT -1 COMMENT 'Viewport X bound at the time the annotation was drawn, when recorded by the source system; -1 when not populated.',
  `window_y` int(11) NOT NULL DEFAULT -1 COMMENT 'Viewport Y bound at the time the annotation was drawn, when recorded by the source system; -1 when not populated.',
  `window_w` int(11) NOT NULL DEFAULT -1 COMMENT 'Viewport width at the time the annotation was drawn, when recorded by the source system; -1 when not populated.',
  `window_h` int(11) NOT NULL DEFAULT -1 COMMENT 'Viewport height at the time the annotation was drawn, when recorded by the source system; -1 when not populated.',
  `arrow_start_x` int(11) NOT NULL DEFAULT -1 COMMENT 'Start-point X for line-shaped annotations (arrow, measure); -1 when not applicable.',
  `arrow_start_y` int(11) NOT NULL DEFAULT -1 COMMENT 'Start-point Y for line-shaped annotations (arrow, measure); -1 when not applicable.',
  `arrow_end_x` int(11) NOT NULL DEFAULT -1 COMMENT 'End-point X for line-shaped annotations (arrow, measure); -1 when not applicable.',
  `arrow_end_y` int(11) NOT NULL DEFAULT -1 COMMENT 'End-point Y for line-shaped annotations (arrow, measure); -1 when not applicable.',
  `zoom` double NOT NULL COMMENT 'View-scale factor recorded at the time the annotation was drawn by the source system; whether coordinates need multiplying by this to reach full-resolution pixels is still being verified (see dih-slide-reconciler HANDOFF.md).',
  `focal_plane` int(10) unsigned NOT NULL DEFAULT 0 COMMENT 'Focal plane index the annotation was drawn on, for multi-focal-plane slides.',
  `current_frame` int(10) unsigned NOT NULL DEFAULT 0 COMMENT 'Frame/view index the annotation was drawn on, for multi-view slides.',
  `title` varchar(255) NOT NULL COMMENT 'Short heading/name for the annotation.',
  `description` varchar(255) NOT NULL COMMENT 'Longer free-text description, may include imported source comments.',
  `annotation_date` timestamp NULL DEFAULT NULL COMMENT 'When the annotation was originally authored in the source system.',
  `line_colour` varchar(255) NOT NULL COMMENT 'Display colour for the annotation outline, as recorded by the source system.',
  `drawing` longtext DEFAULT NULL COMMENT 'Freehand/polygon shape data (HTML-escaped XML with a point list relative to rect_x/rect_y), only populated for annotation_type drawing/polygon.',
  `moveable` varchar(24) NOT NULL COMMENT 'Source system''s movability flag for this annotation object.',
  `area` bigint(20) NOT NULL DEFAULT 0 COMMENT 'Measured area of the annotation, as recorded by the source system.',
  `filled` enum('true','false') NOT NULL DEFAULT 'false' COMMENT 'Whether the annotation shape is rendered filled (''true'') or outline-only (''false'').',
  `invisible` enum('true','false') NOT NULL DEFAULT 'false' COMMENT 'Whether the source system had this annotation marked hidden - real per-annotation data, not something to filter out by default (many slides have some or all annotations marked this way).',
  `tma_core` smallint(5) unsigned DEFAULT NULL COMMENT 'Tissue microarray core index, for TMA slides.',
  `owner` int(11) DEFAULT NULL COMMENT 'Numeric user id of the annotation''s author in the source system (0 = system-recorded, e.g. scanned_region marking the scan bounds rather than a teaching annotation).',
  `source_annotation_id` int(11) DEFAULT NULL COMMENT 'Original annotationId from the legacy dih database, for provenance/audit; NULL for annotations created directly in the app.',
  `created_date` timestamp NULL DEFAULT current_timestamp() COMMENT 'Row creation timestamp in this catalogue.',
  `updated_date` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp() COMMENT 'Row last-updated timestamp in this catalogue.',
  PRIMARY KEY (`annotation_id`),
  KEY `idx_slide_annotations_slide_id` (`slide_id`),
  CONSTRAINT `fk_slide_annotations_slide` FOREIGN KEY (`slide_id`) REFERENCES `slides` (`slide_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Region/point/line annotations attached to a slide - imported from the legacy Slidepath DIH database via dih-slide-reconciler (source_annotation_id preserves the original dih annotationId), or created directly by the app going forward.';

DROP TABLE IF EXISTS `slide_correction_actions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slide_correction_actions` (
  `action_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  `feedback_id` bigint(20) NOT NULL COMMENT 'The slide_corrections row this action was taken against.',
  `slide_id` bigint(20) NOT NULL COMMENT 'Slide the correction concerns, denormalised for convenient querying.',
  `action_type` enum('status_update','metadata_update') NOT NULL COMMENT 'Kind of action performed - status_update (correction''s status changed) or metadata_update (a metadata field was actually applied to the slide).',
  `field_name` varchar(100) DEFAULT NULL COMMENT 'For metadata_update actions, which slide_metadata/slide_tissue_annotations field was changed; for status_update actions, always ''status''.',
  `old_value` text DEFAULT NULL COMMENT 'The value before this action.',
  `new_value` text DEFAULT NULL COMMENT 'The value after this action.',
  `action_notes` text DEFAULT NULL COMMENT 'Free-text notes attached to this specific action.',
  `performed_by_username` varchar(191) NOT NULL COMMENT 'Username of the admin/reviewer who performed this action.',
  `performed_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT 'When this action was performed.',
  PRIMARY KEY (`action_id`),
  KEY `idx_feedback_actions_feedback_id` (`feedback_id`),
  KEY `idx_feedback_actions_slide_id` (`slide_id`),
  KEY `idx_feedback_actions_action_type` (`action_type`),
  KEY `idx_feedback_actions_performed_at` (`performed_at`),
  CONSTRAINT `fk_feedback_actions_feedback` FOREIGN KEY (`feedback_id`) REFERENCES `slide_corrections` (`feedback_id`),
  CONSTRAINT `fk_feedback_actions_slide` FOREIGN KEY (`slide_id`) REFERENCES `slides` (`slide_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Append-only audit log of actions taken against a slide_corrections row - one row per status change or applied metadata update.';

DROP TABLE IF EXISTS `slide_corrections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slide_corrections` (
  `feedback_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  `slide_id` bigint(20) NOT NULL COMMENT 'Slide this feedback concerns.',
  `slide_filename` text DEFAULT NULL COMMENT 'Slide''s filename at submission time, kept for convenient display/export without a join.',
  `feedback_source` enum('metadata','slide_annotation','legacy_note') NOT NULL DEFAULT 'metadata' COMMENT 'Which part of the catalogue this feedback is about - ''metadata'' (organ/species/stain/etc.), ''slide_annotation'' (a reported annotation error), or ''legacy_note'' (an expert contributor note correction).',
  `feedback_type` varchar(100) NOT NULL DEFAULT 'general_comment' COMMENT 'For feedback_source=''metadata'', which field is being corrected (organ, tissue, species, stain, description, notes, general_comment); for feedback_source=''slide_annotation'', always ''annotation_review''.',
  `source_annotation_id` bigint(20) DEFAULT NULL COMMENT 'For feedback_source=''slide_annotation'', the slide_annotations.annotation_id this report concerns.',
  `source_legacy_curation_id` bigint(20) DEFAULT NULL COMMENT 'For feedback_source=''legacy_note'', the related legacy_curation.curation_id this correction concerns.',
  `current_value` text DEFAULT NULL COMMENT 'The value/context being reported on at submission time.',
  `suggested_value` text DEFAULT NULL COMMENT 'The submitter''s suggested replacement value (or, for annotation reports, their verdict: ''correct''/''incorrect'').',
  `feedback_text` text NOT NULL COMMENT 'Free-text explanation/reasoning from the submitter.',
  `submitter_username` varchar(191) NOT NULL COMMENT 'Username of the user who submitted this feedback, captured at submission time.',
  `submitter_email` varchar(255) DEFAULT NULL COMMENT 'Email of the submitting user, captured at submission time.',
  `submitter_display_name` varchar(255) DEFAULT NULL COMMENT 'Display name of the submitting user, captured at submission time.',
  `submitter_role` varchar(50) DEFAULT NULL COMMENT 'Role of the submitting user, captured at submission time (a later role change doesn''t rewrite this).',
  `status` enum('new','under_review','accepted','rejected','resolved') NOT NULL DEFAULT 'new' COMMENT 'Review workflow state - new, under_review, accepted, rejected, or resolved.',
  `admin_notes` text DEFAULT NULL COMMENT 'Reviewer''s notes, added when changing status.',
  `reviewed_by_username` varchar(191) DEFAULT NULL COMMENT 'Username of whoever last changed this correction''s status.',
  `reviewed_at` datetime DEFAULT NULL COMMENT 'When the status was last changed.',
  `remote_addr` varchar(100) DEFAULT NULL COMMENT 'Submitter''s IP address, captured for abuse/audit purposes.',
  `user_agent` varchar(500) DEFAULT NULL COMMENT 'Submitter''s browser user-agent, captured for abuse/audit purposes.',
  `legacy_metadata_feedback_id` bigint(20) DEFAULT NULL COMMENT 'Reference to a pre-migration feedback record, for rows imported from an earlier version of this feature.',
  `created_at` datetime NOT NULL DEFAULT current_timestamp() COMMENT 'Row creation timestamp.',
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp() COMMENT 'Row last-updated timestamp.',
  PRIMARY KEY (`feedback_id`),
  KEY `idx_slide_feedback_slide_id` (`slide_id`),
  KEY `idx_slide_feedback_source` (`feedback_source`),
  KEY `idx_slide_feedback_type` (`feedback_type`),
  KEY `idx_slide_feedback_status` (`status`),
  KEY `idx_slide_feedback_submitter` (`submitter_username`),
  KEY `idx_slide_feedback_created_at` (`created_at`),
  KEY `idx_slide_feedback_legacy_metadata_feedback_id` (`legacy_metadata_feedback_id`),
  KEY `fk_slide_feedback_annotation` (`source_annotation_id`),
  KEY `fk_slide_corrections_legacy` (`source_legacy_curation_id`),
  CONSTRAINT `fk_slide_feedback_annotation` FOREIGN KEY (`source_annotation_id`) REFERENCES `slide_annotations` (`annotation_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_slide_corrections_legacy` FOREIGN KEY (`source_legacy_curation_id`) REFERENCES `legacy_curation` (`curation_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_slide_feedback_slide` FOREIGN KEY (`slide_id`) REFERENCES `slides` (`slide_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='User-submitted feedback/correction reports awaiting admin or reviewer action - covers metadata corrections, reported annotation errors, and expert-note corrections, distinguished by feedback_source.';

DROP TABLE IF EXISTS `slide_legacy_curation_links`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slide_legacy_curation_links` (
  `slide_id` int(11) NOT NULL COMMENT 'Slide identifier',
  `legacy_curation_id` int(11) NOT NULL COMMENT 'References legacy_curation.curation_id.',
  `confidence_score` decimal(5,2) DEFAULT NULL COMMENT 'Curatorial confidence in reconciliation between the slide and its legacy archive record',
  `reconciliation_method` varchar(100) DEFAULT NULL COMMENT 'FILENAME_MATCH, COLLECTION_NAME_MATCH, DOCUMENT_CONTEXT, MANUAL_REVIEW',
  `reconciliation_notes` text DEFAULT NULL COMMENT 'Explanation of why the reconciliation was accepted',
  `created_at` timestamp NULL DEFAULT current_timestamp() COMMENT 'When this reconciliation link was created.',
  PRIMARY KEY (`slide_id`,`legacy_curation_id`),
  KEY `idx_slide_id` (`slide_id`),
  KEY `idx_legacy_curation_id` (`legacy_curation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Reconciliation layer linking slides to preserved legacy archive records. Source annotations remain in database legacy_curation and are referenced through legacy_curation_id for provenance preservation.';

DROP TABLE IF EXISTS `slide_metadata`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slide_metadata` (
  `slide_id` bigint(20) NOT NULL COMMENT 'Slide this metadata belongs to (slides.slide_id).',
  `organ` varchar(255) DEFAULT NULL COMMENT 'Curated organ or anatomical structure for this slide.',
  `species` varchar(255) DEFAULT NULL COMMENT 'Curated species for this slide.',
  `stain` varchar(255) DEFAULT NULL COMMENT 'Curated (or raw, pre-normalisation) stain description for this slide.',
  `magnification` int(11) DEFAULT NULL COMMENT 'Curated primary objective magnification for this slide.',
  `description` text DEFAULT NULL COMMENT 'Free-text description of the slide''s content.',
  `notes` text DEFAULT NULL COMMENT 'Free-text curator notes.',
  `created_date` timestamp NULL DEFAULT current_timestamp() COMMENT 'Row creation timestamp.',
  `updated_date` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp() COMMENT 'Row last-updated timestamp.',
  `is_comparison_slide` tinyint(1) DEFAULT NULL COMMENT 'Teaching/comparison slide. NULL=not assessed or not defined. 0=single specimen with a single preparation. 1=contains multiple specimens and/or preparations intended for side-by-side comparison (e.g. PAS vs H&E, Masson vs H&E).',
  `meaningful_view_count` int(11) DEFAULT NULL COMMENT 'Number of meaningful specimen views present in the slide after vendor-specific normalisation. Derived from crawler metadata. For Leica SCN slides the standard macro image is excluded from the count. NDPI slides with crawler view_count=0 are normalised to a single specimen view. A value greater than 1 indicates a multi-view slide and may be used by catalogue applications to identify and display multi-view slides.',
  `image_dimensions` text DEFAULT NULL COMMENT 'Curated specimen dimensions. For Leica SCN slides the standard macro image (1616x4668) has been removed.',
  `thumbnail_1024_path` text DEFAULT NULL COMMENT 'Path to 1024px generated thumbnail',
  `thumbnail_2048_path` text DEFAULT NULL COMMENT 'Path to 2048px generated thumbnail',
  `thumbnail_512_path` text DEFAULT NULL COMMENT 'Path to 512px generated thumbnail',
  `is_z_stack` tinyint(1) DEFAULT NULL COMMENT 'Crawler v103 detected z-stack image',
  `z_plane_count` int(11) DEFAULT NULL COMMENT 'Number of z-planes detected by crawler v103',
  `legacy_thick_section` tinyint(1) NOT NULL DEFAULT 0 COMMENT 'Identifies legacy thick-section specimens prepared before modern microtomy practices. These slides frequently require z-stacking to maintain focus through specimen depth. Populated through expert review and historical collection knowledge. TRUE=confirmed legacy thick section; FALSE=not identified as a legacy thick section.',
  PRIMARY KEY (`slide_id`),
  CONSTRAINT `fk_slide_metadata_slide` FOREIGN KEY (`slide_id`) REFERENCES `slides` (`slide_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Curated organ/species/stain/description metadata and generated thumbnail paths for a slide - one row per slide_id, distinct from the raw crawler-derived data in slide_technical_metadata.';

DROP TABLE IF EXISTS `slide_technical_metadata`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slide_technical_metadata` (
  `slide_id` bigint(20) NOT NULL COMMENT 'Foreign key to slides.slide_id. One-to-one relationship between a catalogue slide and its crawler-derived technical metadata.',
  `openslide_status` varchar(32) DEFAULT NULL COMMENT 'OpenSlide processing status reported by the crawler.',
  `openslide_vendor` varchar(255) DEFAULT NULL COMMENT 'Slide vendor reported by OpenSlide metadata extraction.',
  `openslide_scan_date` varchar(64) DEFAULT NULL COMMENT 'Scan date reported by OpenSlide metadata extraction.',
  `openslide_quickhash` varchar(255) DEFAULT NULL COMMENT 'OpenSlide-generated quickhash. Only available when OpenSlide successfully processes a slide. Known SCN_MULTIIMAGE slides return NULL because OpenSlide processing fails.',
  `openslide_associated_image_count` int(11) DEFAULT NULL COMMENT 'Number of associated images reported by OpenSlide metadata extraction.',
  `tiffslide_status` varchar(32) DEFAULT NULL COMMENT 'TiffSlide processing status reported by the crawler.',
  `tiffslide_vendor` varchar(255) DEFAULT NULL COMMENT 'Slide vendor reported by TiffSlide metadata extraction.',
  `openslide_mpp_x` decimal(18,15) DEFAULT NULL COMMENT 'Microns per pixel on the X axis reported by OpenSlide metadata extraction.',
  `openslide_mpp_y` decimal(18,15) DEFAULT NULL COMMENT 'Microns per pixel on the Y axis reported by OpenSlide metadata extraction.',
  `tiffslide_mpp_x` decimal(18,15) DEFAULT NULL COMMENT 'Microns per pixel on the X axis reported by TiffSlide metadata extraction.',
  `tiffslide_mpp_y` decimal(18,15) DEFAULT NULL COMMENT 'Microns per pixel on the Y axis reported by TiffSlide metadata extraction.',
  `collection_name` text DEFAULT NULL COMMENT 'Embedded slide metadata title recovered by crawler extraction. May be useful for validation of organ, species, stain and description metadata but is not considered authoritative catalogue metadata.',
  `image_count` varchar(32) DEFAULT NULL COMMENT 'Raw image count reported by the crawler before catalogue normalisation.',
  `image_names` longtext DEFAULT NULL COMMENT 'Raw image names reported by the crawler.',
  `is_multiview` varchar(10) DEFAULT NULL COMMENT 'Raw crawler flag indicating multiple image views or image series. Retained for provenance and audit purposes.',
  `view_count` varchar(32) DEFAULT NULL COMMENT 'Raw crawler view count retained for provenance. Catalogue applications should use slide_metadata.meaningful_view_count instead.',
  `z_spacing` varchar(64) DEFAULT NULL COMMENT 'Raw crawler z_spacing value retained for provenance. Investigation showed populated values occur on Leica SCN slides and not on true z-stack slides.',
  `technical_metadata_source` varchar(64) DEFAULT NULL COMMENT 'Source inventory used to populate the record, for example crawler_v103.',
  `technical_metadata_updated` timestamp NULL DEFAULT current_timestamp() COMMENT 'Timestamp when technical metadata was last imported or refreshed.',
  PRIMARY KEY (`slide_id`),
  CONSTRAINT `fk_slide_technical_metadata_slide` FOREIGN KEY (`slide_id`) REFERENCES `slides` (`slide_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Technical metadata extracted from virtual slide files during crawler operations. The crawler uses both OpenSlide and TiffSlide to interrogate slide files and extract scanner, acquisition, calibration and image-structure metadata. This table preserves crawler-derived metadata that is not part of the curated catalogue metadata model but may be required for provenance, validation, image calibration, quality assurance, future migrations and recrawling activities. Data originates from crawler inventory imports including v102 and v103. Future crawler runs should update represented fields in this table rather than adding crawler-derived metadata directly to slides, slide_metadata or slide_annotations unless the field becomes part of the authoritative catalogue metadata model.';

DROP TABLE IF EXISTS `slide_tissue_annotations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slide_tissue_annotations` (
  `slide_id` bigint(20) NOT NULL COMMENT 'Slide identifier from slides.slide_id',
  `tissue_id` int(11) NOT NULL COMMENT 'Canonical tissue identifier from tissue_dictionary.tissue_id',
  `evidence_source` varchar(100) DEFAULT NULL COMMENT 'Source of tissue assignment, e.g. metadata, filename, legacy contributor, manual review',
  `review_status` varchar(50) DEFAULT NULL COMMENT 'Curation status of this slide-tissue assignment',
  `confidence` varchar(20) DEFAULT NULL COMMENT 'Confidence in this slide-tissue assignment',
  `notes` text DEFAULT NULL COMMENT 'Additional curator notes',
  `created_date` timestamp NULL DEFAULT current_timestamp() COMMENT 'When this slide-tissue assignment was created.',
  PRIMARY KEY (`slide_id`,`tissue_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Permanent curated table linking slides to canonical tissues or histological structures.';

DROP TABLE IF EXISTS `slides`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slides` (
  `slide_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Primary key, referenced by nearly every other slide-scoped table.',
  `inventory_id` bigint(20) DEFAULT NULL COMMENT 'Legacy identifier from the pre-catalogue crawler inventory, kept for provenance/cross-referencing with older exports.',
  `filename` text NOT NULL COMMENT 'The slide''s own filename as found on disk (not necessarily unique across the archive).',
  `physical_path` text NOT NULL COMMENT 'Full server-side filesystem path used by the application to open the slide file directly.',
  `archive_relative_path` text DEFAULT NULL COMMENT 'Path relative to the archive share root (e.g. "Archive/..."), used to build share links for different OS mount points.',
  `slide_format` varchar(20) DEFAULT NULL COMMENT 'File extension/format of the slide (e.g. NDPI, SCN, SVS).',
  `file_size_bytes` bigint(20) DEFAULT NULL COMMENT 'Size of the slide file on disk, in bytes.',
  `width_pixels` int(11) DEFAULT NULL COMMENT 'Full-resolution (level 0) pixel width of the slide image.',
  `height_pixels` int(11) DEFAULT NULL COMMENT 'Full-resolution (level 0) pixel height of the slide image.',
  `metadata_status` enum('MATCHED_METADATA','NO_METADATA') NOT NULL COMMENT 'Whether this slide has been matched to curated metadata (MATCHED_METADATA) or still needs it (NO_METADATA).',
  `asset_status` enum('ACTIVE','SCN_MULTIIMAGE','CORRUPT_FILE','UNUSABLE_SCAN','DUPLICATE_SLIDE') NOT NULL DEFAULT 'ACTIVE' COMMENT 'Asset disposition. ACTIVE=normal catalogue slide; SCN_MULTIIMAGE=multi-image SCN reconciled via SQLite metadata; CORRUPT_FILE=known unreadable slide; UNUSABLE_SCAN=valid file unsuitable for teaching use; DUPLICATE_SLIDE=superseded by another slide.',
  `created_date` timestamp NULL DEFAULT current_timestamp() COMMENT 'When this slide record was first inserted into the catalogue.',
  `objective_magnifications` varchar(20) DEFAULT NULL COMMENT 'Objective magnifications identified for the slide from crawler-derived metadata and manual validation where required. Single-view slides typically contain a single value (e.g. 20x or 40x). Some multiview slides contain image views acquired at different objective magnifications. In these cases multiple values are stored (e.g. 20x;40x). This reflects historical scanning practice where selected regions of interest were occasionally scanned at higher magnification than other areas of the same slide.',
  PRIMARY KEY (`slide_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Core catalogue record for one virtual slide file - one row per slide, joined by slide_id to slide_metadata, slide_technical_metadata, slide_annotations, and the various correction/feedback tables.';

DROP TABLE IF EXISTS `slides_to_be_deleted_review`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slides_to_be_deleted_review` (
  `deletion_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'Unique identifier for duplicate-review and deletion-tracking records.',
  `slide_id` bigint(20) DEFAULT NULL COMMENT 'Slide identified as a potential duplicate. NULL for historical removals recorded before slide-level tracking was introduced.',
  `keep_slide_id` bigint(20) DEFAULT NULL COMMENT 'Current preferred slide to retain when multiple slide records represent the same biological specimen. This is a curator preference and may change following later review.',
  `physical_filename` text DEFAULT NULL COMMENT 'Filename of the candidate duplicate slide.',
  `physical_path` text DEFAULT NULL COMMENT 'Storage location of the candidate duplicate slide at the time the record was created.',
  `reason` varchar(255) DEFAULT NULL COMMENT 'Reason the slide was identified as a duplicate or removal candidate. Examples include lower magnification scan, duplicate acquisition, superseded image quality, or duplicate biological specimen.',
  `has_metadata` enum('YES','NO','UNKNOWN') DEFAULT 'UNKNOWN' COMMENT 'Indicates whether associated records may exist in slide_metadata and should be reviewed before deletion.',
  `has_annotations` enum('YES','NO','UNKNOWN') DEFAULT 'UNKNOWN' COMMENT 'Indicates whether associated annotation records may exist and should be reviewed before deletion.',
  `has_technical_metadata` enum('YES','NO','UNKNOWN') DEFAULT 'UNKNOWN' COMMENT 'Indicates whether crawler-derived records may exist in slide_technical_metadata and should be reviewed before deletion.',
  `deletion_status` enum('PENDING_REVIEW','APPROVED_FOR_REMOVAL','REMOVED') NOT NULL DEFAULT 'PENDING_REVIEW' COMMENT 'Duplicate-review lifecycle. PENDING_REVIEW = identified but not yet confirmed. APPROVED_FOR_REMOVAL = curator review completed and approved for storage deletion. REMOVED = file removed and associated catalogue cleanup completed.',
  `review_notes` text DEFAULT NULL COMMENT 'Free-text curator notes, review findings, transfer requirements, metadata considerations, annotation considerations, or rationale for retaining a preferred slide.',
  PRIMARY KEY (`deletion_id`),
  KEY `idx_slide_id` (`slide_id`),
  KEY `idx_keep_slide_id` (`keep_slide_id`),
  KEY `idx_deletion_status` (`deletion_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Temporary curation table listing slides proposed for deletion or exclusion.';

DROP TABLE IF EXISTS `species_dictionary`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `species_dictionary` (
  `species_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  `species_name` varchar(255) NOT NULL COMMENT 'Raw/original species name as it appears in source data before normalisation.',
  `scientific_name` varchar(255) DEFAULT NULL COMMENT 'Latin binomial/scientific name for this species.',
  `active` tinyint(1) DEFAULT 1 COMMENT 'Whether this dictionary entry is currently in active use (0 = retired/superseded).',
  `notes` text DEFAULT NULL COMMENT 'Free-text curator notes.',
  `canonical_species` varchar(255) DEFAULT NULL COMMENT 'Preferred canonical species name.',
  `species_group` varchar(255) DEFAULT NULL COMMENT 'Broad grouping used for search and reconciliation (e.g. mammal, avian).',
  `normalisation_status` varchar(50) DEFAULT NULL COMMENT 'Status of dictionary normalisation, e.g. NORMALISED, REVIEW, EXCLUDED.',
  `also_known_as` text DEFAULT NULL COMMENT 'Comma-separated aliases, abbreviations, spelling variants, or legacy labels.',
  `review_status` varchar(50) DEFAULT NULL COMMENT 'Dictionary curation status, e.g. APPROVED, PENDING, REVIEW.',
  `confidence` varchar(20) DEFAULT NULL COMMENT 'Confidence in the canonical mapping, e.g. HIGH, MEDIUM, LOW.',
  PRIMARY KEY (`species_id`),
  UNIQUE KEY `uq_species_name` (`species_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Controlled vocabulary for species associated with slides, annotations and reconciliation workflows.';

DROP TABLE IF EXISTS `stain_dictionary`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `stain_dictionary` (
  `original_stain` varchar(255) NOT NULL COMMENT 'Original stain value as found in slide_metadata.stain or source material. This may include typos, abbreviations, historical spellings, composite stains, comparison-slide labels, or imported artefacts. Primary key.',
  `canonical_stain` varchar(255) DEFAULT NULL COMMENT 'Preferred normalised stain term for search, filtering, and metadata display. Should preserve meaningful composite or comparison terminology where appropriate rather than flattening biologically useful information.',
  `stain_family` varchar(255) DEFAULT NULL COMMENT 'Broad stain or technique family, for example Routine Histology, Trichrome, Silver, Neurohistology, Lipid Stain, Blood Stain, Elastic, Histochemistry, or Injection/Preparation technique.',
  `normalisation_status` varchar(50) DEFAULT NULL COMMENT 'Status of the mapping between original_stain and canonical_stain, for example Canonical, Normalised, Historical Preserved, Needs Review, or Not a stain.',
  `notes` text DEFAULT NULL COMMENT 'Curatorial notes explaining the stain, historical terminology, interpretation decisions, or reasons for preserving a specific original value.',
  `also_known_as` text DEFAULT NULL COMMENT 'Aliases, abbreviations, spelling variants, historical names, OCR/import variants, and common typos associated with the canonical stain.',
  `visual_clues` text DEFAULT NULL COMMENT 'Expected visual or histological staining features useful for manual review, quality control, or future image-based validation.',
  `review_status` varchar(50) DEFAULT NULL COMMENT 'Curatorial review state of this dictionary entry, for example Approved, Needs Review, Provisional, Rejected, or Deprecated.',
  `confidence` varchar(20) DEFAULT NULL COMMENT 'Confidence level for the normalisation decision, for example High, Medium, or Low.',
  `typical_applications` text DEFAULT NULL COMMENT 'Typical tissues, structures, or teaching contexts where this stain or technique is commonly used.',
  PRIMARY KEY (`original_stain`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Curated stain normalisation dictionary. Maps original stain strings found in slide_metadata.stain, filenames, and legacy sources to canonical stain terminology while preserving aliases, historical names, composite stains, review status, confidence, and explanatory notes.';

DROP TABLE IF EXISTS `system_settings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `system_settings` (
  `setting_name` varchar(100) NOT NULL COMMENT 'Primary key - the setting''s identifier.',
  `setting_value` text NOT NULL COMMENT 'The setting''s current value, stored as text.',
  `updated_by` varchar(100) DEFAULT NULL COMMENT 'Username of the admin who last changed this setting.',
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp() COMMENT 'When this setting was last changed.',
  PRIMARY KEY (`setting_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Simple key-value store for admin-configurable application settings.';

DROP TABLE IF EXISTS `tissue_dictionary`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `tissue_dictionary` (
  `tissue_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  `tissue_name` varchar(255) NOT NULL COMMENT 'Raw/original tissue name as it appears in source data before normalisation.',
  `tissue_category` varchar(255) DEFAULT NULL COMMENT 'Broader histological category this tissue belongs to.',
  `active` tinyint(1) DEFAULT 1 COMMENT 'Whether this dictionary entry is currently in active use (0 = retired/superseded).',
  `notes` text DEFAULT NULL COMMENT 'Free-text curator notes.',
  `canonical_tissue` varchar(255) DEFAULT NULL COMMENT 'Preferred canonical tissue or histological structure name',
  `tissue_group` varchar(255) DEFAULT NULL COMMENT 'Broad tissue class or histological grouping',
  `normalisation_status` varchar(50) DEFAULT NULL COMMENT 'Status of dictionary normalisation, e.g. NORMALISED, REVIEW, EXCLUDED',
  `also_known_as` text DEFAULT NULL COMMENT 'Comma-separated aliases, abbreviations, spelling variants, or legacy labels',
  `review_status` varchar(50) DEFAULT NULL COMMENT 'Dictionary curation status, e.g. APPROVED, PENDING, REVIEW',
  `confidence` varchar(20) DEFAULT NULL COMMENT 'Confidence in the canonical mapping, e.g. HIGH, MEDIUM, LOW',
  PRIMARY KEY (`tissue_id`),
  UNIQUE KEY `uq_tissue_name` (`tissue_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Permanent dictionary of canonical tissues, histological tissue classes, and microscopic anatomical structures.';

DROP TABLE IF EXISTS `user_activation_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_activation_tokens` (
  `token_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  `user_id` int(11) NOT NULL COMMENT 'The users.user_id this token was issued for.',
  `activation_token` char(36) NOT NULL COMMENT 'The single-use token value emailed to the user.',
  `created_at` timestamp NULL DEFAULT current_timestamp() COMMENT 'When the token was issued.',
  `expires_at` timestamp NULL DEFAULT NULL COMMENT 'When the token stops being valid.',
  `used_at` timestamp NULL DEFAULT NULL COMMENT 'When the token was redeemed; NULL if not yet used.',
  PRIMARY KEY (`token_id`),
  UNIQUE KEY `activation_token` (`activation_token`),
  KEY `fk_activation_user` (`user_id`),
  CONSTRAINT `fk_activation_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Single-use, time-limited tokens issued to newly-approved accounts to set their initial password and activate.';

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `user_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Primary key.',
  `username` varchar(255) NOT NULL COMMENT 'Unique login identifier.',
  `email` varchar(255) NOT NULL COMMENT 'Unique email address, used for notifications and password reset.',
  `full_name` varchar(255) NOT NULL COMMENT 'Display name.',
  `institution` varchar(255) DEFAULT NULL COMMENT 'Self-reported institution/affiliation.',
  `guid` varchar(64) DEFAULT NULL COMMENT 'External identity provider GUID, for LDAP-authenticated accounts.',
  `role` enum('user','admin','system_admin','reviewer','expert') NOT NULL DEFAULT 'user' COMMENT 'Access level - user, admin, system_admin (full access, DB-assignable only), reviewer (corrections.view/review permissions), or expert (expert_notes.write permission). See role_permissions.',
  `authentication_method` enum('LOCAL','LDAP') NOT NULL DEFAULT 'LOCAL' COMMENT 'Whether this account logs in with a local password (LOCAL) or an institutional LDAP account (LDAP).',
  `account_status` enum('PENDING_ACTIVATION','ACTIVE','DISABLED') NOT NULL DEFAULT 'PENDING_ACTIVATION' COMMENT 'PENDING_ACTIVATION (approved but not yet activated), ACTIVE, or DISABLED.',
  `contributions_count` int(11) NOT NULL DEFAULT 0 COMMENT 'Total number of feedback/correction submissions made by this user.',
  `contributions_accepted_count` int(11) NOT NULL DEFAULT 0 COMMENT 'Number of this user''s submissions that were acted on (resolved).',
  `password_hash` text DEFAULT NULL COMMENT 'Argon2 hash of the account''s local password; NULL for LDAP-authenticated accounts.',
  `approved_by` varchar(100) DEFAULT NULL COMMENT 'Username of the admin who approved this account''s access request.',
  `approved_at` timestamp NULL DEFAULT NULL COMMENT 'When this account''s access request was approved.',
  `created_at` timestamp NULL DEFAULT current_timestamp() COMMENT 'When this user record was created.',
  `last_login_at` datetime DEFAULT NULL COMMENT 'Timestamp of this user''s most recent successful login.',
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Catalogue user accounts - local or LDAP-authenticated, with a role controlling what they can see and do (see role_permissions for reviewer/expert capabilities).';

SET FOREIGN_KEY_CHECKS=1;

-- Two views used by the app (v_slide_legacy_notes, queried directly by
-- get_slide/search_slides) and kept for convenience (v_slide_catalogue_app,
-- a flattened slide+metadata+stain view for ad-hoc reporting/Adminer use -
-- not queried by the app itself). Neither was captured in any prior dump or
-- migration; both were reconstructed here from the live view definitions.

DROP VIEW IF EXISTS `v_slide_legacy_notes`;
CREATE VIEW `v_slide_legacy_notes` AS
SELECT
  `s`.`slide_id` AS `slide_id`,
  `s`.`filename` AS `filename`,
  `d`.`curation_id` AS `legacy_curation_id`,
  `d`.`annotation_title` AS `annotation_title`,
  `d`.`note_text` AS `note_text`,
  `sda`.`confidence_score` AS `confidence_score`,
  `sda`.`reconciliation_method` AS `reconciliation_method`,
  `sda`.`reconciliation_notes` AS `reconciliation_notes`
FROM (`slide_legacy_curation_links` `sda`
  JOIN `slides` `s` ON (`s`.`slide_id` = `sda`.`slide_id`))
  JOIN `legacy_curation` `d` ON (`d`.`curation_id` = `sda`.`legacy_curation_id`);

DROP VIEW IF EXISTS `v_slide_catalogue_app`;
CREATE VIEW `v_slide_catalogue_app` AS
SELECT
  `s`.`slide_id` AS `slide_id`,
  `s`.`filename` AS `filename`,
  `sm`.`organ` AS `organ`,
  `sm`.`species` AS `species`,
  `sm`.`stain` AS `raw_stain`,
  `sd`.`canonical_stain` AS `canonical_stain`,
  `sd`.`stain_family` AS `stain_family`,
  `sm`.`description` AS `description`
FROM (`slides` `s`
  LEFT JOIN `slide_metadata` `sm` ON (`sm`.`slide_id` = `s`.`slide_id`))
  LEFT JOIN `stain_dictionary` `sd` ON (`sd`.`original_stain` = `sm`.`stain`);
