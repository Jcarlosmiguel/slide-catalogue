-- Base schema for the catalogue database (26 tables), extracted from a
-- production schema dump with all data stripped - CREATE TABLE only.
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
  `attempt_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `attempted_email` varchar(255) NOT NULL,
  `attempted_full_name` varchar(255) DEFAULT NULL,
  `reason` enum('email_already_registered','duplicate_pending_request') NOT NULL,
  `remote_addr` varchar(100) DEFAULT NULL,
  `user_agent` varchar(500) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`attempt_id`),
  KEY `idx_attempted_email` (`attempted_email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

DROP TABLE IF EXISTS `access_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `access_requests` (
  `request_id` int(11) NOT NULL AUTO_INCREMENT,
  `full_name` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `institution` varchar(255) NOT NULL,
  `guid` varchar(64) DEFAULT NULL,
  `authentication_method` enum('LOCAL','LDAP') NOT NULL DEFAULT 'LOCAL',
  `request_reason` text NOT NULL,
  `status` enum('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'PENDING',
  `submitted_at` timestamp NULL DEFAULT current_timestamp(),
  `reviewed_at` timestamp NULL DEFAULT NULL,
  `reviewed_by` varchar(100) DEFAULT NULL,
  `review_notes` text DEFAULT NULL,
  PRIMARY KEY (`request_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

DROP TABLE IF EXISTS `annotation_contributors`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `annotation_contributors` (
  `contributor_id` int(11) NOT NULL,
  `first_name` varchar(255) DEFAULT NULL,
  `surname` varchar(255) DEFAULT NULL,
  `source_system` varchar(100) DEFAULT NULL,
  `notes` text DEFAULT NULL,
  PRIMARY KEY (`contributor_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

DROP TABLE IF EXISTS `david_jenkinson_curation`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `david_jenkinson_curation` (
  `curation_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `source_file` varchar(500) NOT NULL COMMENT 'Original source document from the David Jenkinson archive.',
  `source_authorship` varchar(255) NOT NULL DEFAULT 'David Jenkinson' COMMENT 'Original authorship attribution for the source material.',
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
  `slide_name` varchar(255) DEFAULT NULL COMMENT 'David Jenkinson local catalogue designation, e.g. Kidney 1, Trachea 4, Pancreas 8.',
  `annotation_title` varchar(500) DEFAULT NULL COMMENT 'Title or feature heading associated with the annotation text.',
  `source_archive` varchar(255) DEFAULT NULL COMMENT 'Archive grouping from which the source document originated within the David Jenkinson curation archive.',
  PRIMARY KEY (`curation_id`),
  KEY `idx_source_file` (`source_file`),
  KEY `idx_slide_reference` (`slide_reference`),
  KEY `idx_matched_slide_id` (`matched_slide_id`),
  KEY `idx_record_type` (`record_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Curated David Jenkinson annotation records and note text linked to slides through slide_david_annotations.';

DROP TABLE IF EXISTS `david_record_slide_links`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `david_record_slide_links` (
  `david_record_id` bigint(20) NOT NULL,
  `slide_id` bigint(20) NOT NULL,
  `confidence_score` decimal(5,2) DEFAULT NULL,
  `link_method` varchar(100) DEFAULT NULL,
  `notes` text DEFAULT NULL,
  PRIMARY KEY (`david_record_id`,`slide_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

DROP TABLE IF EXISTS `david_slide_match_stage`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `david_slide_match_stage` (
  `curation_id` bigint(20) NOT NULL,
  `candidate_slide_id` bigint(20) NOT NULL,
  `david_slide_reference` varchar(255) DEFAULT NULL,
  `david_organ` varchar(255) DEFAULT NULL,
  `david_species` varchar(255) DEFAULT NULL,
  `david_stain` varchar(255) DEFAULT NULL,
  `david_tissue` varchar(255) DEFAULT NULL,
  `catalogue_organ` varchar(255) DEFAULT NULL,
  `catalogue_species` varchar(255) DEFAULT NULL,
  `catalogue_stain` varchar(255) DEFAULT NULL,
  `catalogue_tissue` varchar(255) DEFAULT NULL,
  `match_method` varchar(100) NOT NULL,
  `identity_confidence` decimal(5,2) DEFAULT NULL,
  `tissue_match` tinyint(1) DEFAULT 0,
  `stain_match` tinyint(1) DEFAULT 0,
  `organ_match` tinyint(1) DEFAULT 0,
  `species_match` tinyint(1) DEFAULT 0,
  `review_status` varchar(50) DEFAULT 'PENDING',
  `match_notes` text DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`curation_id`,`candidate_slide_id`,`match_method`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Staging table for many-to-many matching of legacy contributor records to slide_id values. Only approved rows should be inserted into slide_david_annotations.';

DROP TABLE IF EXISTS `duplicate_slide_mapping`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `duplicate_slide_mapping` (
  `duplicate_slide_id` bigint(20) NOT NULL,
  `canonical_slide_id` bigint(20) NOT NULL,
  `duplicate_crawler_id` bigint(20) DEFAULT NULL,
  `reason` varchar(255) DEFAULT NULL,
  `evidence` text DEFAULT NULL,
  `created_date` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`duplicate_slide_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Temporary curation table for suspected or confirmed duplicate slide mappings.';

DROP TABLE IF EXISTS `organ_dictionary`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `organ_dictionary` (
  `organ_id` int(11) NOT NULL AUTO_INCREMENT,
  `organ_name` varchar(255) NOT NULL,
  `organ_system` varchar(255) DEFAULT NULL,
  `active` tinyint(1) DEFAULT 1,
  `notes` text DEFAULT NULL,
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
  `organ_id` int(11) NOT NULL,
  `tissue_id` int(11) NOT NULL,
  `notes` text DEFAULT NULL,
  `relationship_type` varchar(100) DEFAULT NULL COMMENT 'Nature of organ-tissue relationship, e.g. CONTAINS, REGION_OF, ASSOCIATED_WITH',
  `review_status` varchar(50) DEFAULT NULL COMMENT 'Curation status of this organ-tissue relationship',
  `confidence` varchar(20) DEFAULT NULL COMMENT 'Confidence in this relationship, e.g. HIGH, MEDIUM, LOW',
  PRIMARY KEY (`organ_id`,`tissue_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Permanent bridge table describing curated relationships between canonical organs and canonical tissues.';

DROP TABLE IF EXISTS `password_reset_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `password_reset_log` (
  `log_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `email_provided` varchar(255) NOT NULL,
  `event_type` enum('requested','completed','invalid_email','inactive_account') NOT NULL,
  `remote_addr` varchar(100) DEFAULT NULL,
  `user_agent` varchar(500) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`log_id`),
  KEY `idx_email_provided` (`email_provided`),
  KEY `fk_password_reset_log_user` (`user_id`),
  CONSTRAINT `fk_password_reset_log_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

DROP TABLE IF EXISTS `password_reset_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `password_reset_tokens` (
  `token_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `reset_token` char(36) NOT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `expires_at` timestamp NULL DEFAULT NULL,
  `used_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`token_id`),
  UNIQUE KEY `reset_token` (`reset_token`),
  KEY `fk_password_reset_user` (`user_id`),
  CONSTRAINT `fk_password_reset_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

DROP TABLE IF EXISTS `slide_annotations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slide_annotations` (
  `annotation_id` bigint(20) NOT NULL,
  `slide_id` bigint(20) NOT NULL,
  `annotation_type` varchar(128) NOT NULL,
  `rect_x` int(11) NOT NULL DEFAULT -1,
  `rect_y` int(11) NOT NULL DEFAULT -1,
  `rect_w` int(11) NOT NULL DEFAULT -1,
  `rect_h` int(11) NOT NULL DEFAULT -1,
  `window_x` int(11) NOT NULL DEFAULT -1,
  `window_y` int(11) NOT NULL DEFAULT -1,
  `window_w` int(11) NOT NULL DEFAULT -1,
  `window_h` int(11) NOT NULL DEFAULT -1,
  `arrow_start_x` int(11) NOT NULL DEFAULT -1,
  `arrow_start_y` int(11) NOT NULL DEFAULT -1,
  `arrow_end_x` int(11) NOT NULL DEFAULT -1,
  `arrow_end_y` int(11) NOT NULL DEFAULT -1,
  `zoom` double NOT NULL,
  `focal_plane` int(10) unsigned NOT NULL DEFAULT 0,
  `current_frame` int(10) unsigned NOT NULL DEFAULT 0,
  `title` varchar(255) NOT NULL,
  `description` varchar(255) NOT NULL,
  `annotation_date` timestamp NULL DEFAULT NULL,
  `line_colour` varchar(255) NOT NULL,
  `drawing` longtext DEFAULT NULL,
  `moveable` varchar(24) NOT NULL,
  `area` bigint(20) NOT NULL DEFAULT 0,
  `filled` enum('true','false') NOT NULL DEFAULT 'false',
  `invisible` enum('true','false') NOT NULL DEFAULT 'false',
  `tma_core` smallint(5) unsigned DEFAULT NULL,
  `owner` int(11) DEFAULT NULL,
  `source_annotation_id` int(11) DEFAULT NULL,
  `created_date` timestamp NULL DEFAULT current_timestamp(),
  `updated_date` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`annotation_id`),
  KEY `idx_slide_annotations_slide_id` (`slide_id`),
  CONSTRAINT `fk_slide_annotations_slide` FOREIGN KEY (`slide_id`) REFERENCES `slides` (`slide_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

DROP TABLE IF EXISTS `slide_david_annotations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slide_david_annotations` (
  `slide_id` int(11) NOT NULL COMMENT 'Slide identifier',
  `david_record_id` int(11) NOT NULL COMMENT 'References david_jenkinson_curation.david_jenkinson_curation_records.david_record_id',
  `confidence_score` decimal(5,2) DEFAULT NULL COMMENT 'Curatorial confidence in reconciliation between the slide and its legacy archive record',
  `reconciliation_method` varchar(100) DEFAULT NULL COMMENT 'FILENAME_MATCH, COLLECTION_NAME_MATCH, DOCUMENT_CONTEXT, MANUAL_REVIEW',
  `reconciliation_notes` text DEFAULT NULL COMMENT 'Explanation of why the reconciliation was accepted',
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`slide_id`,`david_record_id`),
  KEY `idx_slide_id` (`slide_id`),
  KEY `idx_david_record_id` (`david_record_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Reconciliation layer linking slides to preserved legacy archive records. Source annotations remain in database david_jenkinson_curation and are referenced through david_record_id for provenance preservation.';

DROP TABLE IF EXISTS `slide_corrections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slide_corrections` (
  `feedback_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `slide_id` bigint(20) NOT NULL,
  `slide_filename` text DEFAULT NULL,
  `feedback_source` enum('metadata','slide_annotation','david_note') NOT NULL DEFAULT 'metadata',
  `feedback_type` varchar(100) NOT NULL DEFAULT 'general_comment',
  `source_annotation_id` bigint(20) DEFAULT NULL,
  `source_david_record_id` bigint(20) DEFAULT NULL,
  `current_value` text DEFAULT NULL,
  `suggested_value` text DEFAULT NULL,
  `feedback_text` text NOT NULL,
  `submitter_username` varchar(191) NOT NULL,
  `submitter_email` varchar(255) DEFAULT NULL,
  `submitter_display_name` varchar(255) DEFAULT NULL,
  `submitter_role` varchar(50) DEFAULT NULL,
  `status` enum('new','under_review','accepted','rejected','resolved') NOT NULL DEFAULT 'new',
  `admin_notes` text DEFAULT NULL,
  `reviewed_by_username` varchar(191) DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `remote_addr` varchar(100) DEFAULT NULL,
  `user_agent` varchar(500) DEFAULT NULL,
  `legacy_metadata_feedback_id` bigint(20) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`feedback_id`),
  KEY `idx_slide_corrections_slide_id` (`slide_id`),
  KEY `idx_slide_corrections_source` (`feedback_source`),
  KEY `idx_slide_corrections_type` (`feedback_type`),
  KEY `idx_slide_corrections_status` (`status`),
  KEY `idx_slide_corrections_submitter` (`submitter_username`),
  KEY `idx_slide_corrections_created_at` (`created_at`),
  KEY `idx_slide_corrections_legacy_metadata_feedback_id` (`legacy_metadata_feedback_id`),
  KEY `fk_slide_corrections_annotation` (`source_annotation_id`),
  KEY `fk_slide_corrections_david` (`source_david_record_id`),
  CONSTRAINT `fk_slide_corrections_annotation` FOREIGN KEY (`source_annotation_id`) REFERENCES `slide_annotations` (`annotation_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_slide_corrections_david` FOREIGN KEY (`source_david_record_id`) REFERENCES `david_jenkinson_curation` (`curation_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_slide_corrections_slide` FOREIGN KEY (`slide_id`) REFERENCES `slides` (`slide_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

DROP TABLE IF EXISTS `slide_correction_actions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slide_correction_actions` (
  `action_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `feedback_id` bigint(20) NOT NULL,
  `slide_id` bigint(20) NOT NULL,
  `action_type` enum('status_update','metadata_update') NOT NULL,
  `field_name` varchar(100) DEFAULT NULL,
  `old_value` text DEFAULT NULL,
  `new_value` text DEFAULT NULL,
  `action_notes` text DEFAULT NULL,
  `performed_by_username` varchar(191) NOT NULL,
  `performed_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`action_id`),
  KEY `idx_correction_actions_feedback_id` (`feedback_id`),
  KEY `idx_correction_actions_slide_id` (`slide_id`),
  KEY `idx_correction_actions_action_type` (`action_type`),
  KEY `idx_correction_actions_performed_at` (`performed_at`),
  CONSTRAINT `fk_correction_actions_feedback` FOREIGN KEY (`feedback_id`) REFERENCES `slide_corrections` (`feedback_id`),
  CONSTRAINT `fk_correction_actions_slide` FOREIGN KEY (`slide_id`) REFERENCES `slides` (`slide_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

DROP TABLE IF EXISTS `site_feedback`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `site_feedback` (
  `feedback_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `feedback_text` text NOT NULL,
  `page_url` varchar(500) DEFAULT NULL,
  `submitter_username` varchar(191) NOT NULL,
  `submitter_email` varchar(255) DEFAULT NULL,
  `submitter_display_name` varchar(255) DEFAULT NULL,
  `submitter_role` varchar(50) DEFAULT NULL,
  `status` enum('new','under_review','accepted','rejected','resolved') NOT NULL DEFAULT 'new',
  `admin_notes` text DEFAULT NULL,
  `reviewed_by_username` varchar(191) DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `remote_addr` varchar(100) DEFAULT NULL,
  `user_agent` varchar(500) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`feedback_id`),
  KEY `idx_site_feedback_status` (`status`),
  KEY `idx_site_feedback_submitter` (`submitter_username`),
  KEY `idx_site_feedback_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='General free-text feedback about the catalogue site/UX, not tied to a specific slide or correction.';

DROP TABLE IF EXISTS `slide_metadata`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slide_metadata` (
  `slide_id` bigint(20) NOT NULL,
  `organ` varchar(255) DEFAULT NULL,
  `species` varchar(255) DEFAULT NULL,
  `stain` varchar(255) DEFAULT NULL,
  `magnification` int(11) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `notes` text DEFAULT NULL,
  `created_date` timestamp NULL DEFAULT current_timestamp(),
  `updated_date` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

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
  `evidence_source` varchar(100) DEFAULT NULL COMMENT 'Source of tissue assignment, e.g. metadata, filename, David Jenkinson, manual review',
  `review_status` varchar(50) DEFAULT NULL COMMENT 'Curation status of this slide-tissue assignment',
  `confidence` varchar(20) DEFAULT NULL COMMENT 'Confidence in this slide-tissue assignment',
  `notes` text DEFAULT NULL COMMENT 'Additional curator notes',
  `created_date` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`slide_id`,`tissue_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='Permanent curated table linking slides to canonical tissues or histological structures.';

DROP TABLE IF EXISTS `slides`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `slides` (
  `slide_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `inventory_id` bigint(20) DEFAULT NULL,
  `filename` text NOT NULL,
  `physical_path` text NOT NULL,
  `archive_relative_path` text DEFAULT NULL,
  `slide_format` varchar(20) DEFAULT NULL,
  `file_size_bytes` bigint(20) DEFAULT NULL,
  `width_pixels` int(11) DEFAULT NULL,
  `height_pixels` int(11) DEFAULT NULL,
  `metadata_status` enum('MATCHED_METADATA','NO_METADATA') NOT NULL,
  `asset_status` enum('ACTIVE','SCN_MULTIIMAGE','CORRUPT_FILE','UNUSABLE_SCAN','DUPLICATE_SLIDE') NOT NULL DEFAULT 'ACTIVE' COMMENT 'Asset disposition. ACTIVE=normal catalogue slide; SCN_MULTIIMAGE=multi-image SCN reconciled via SQLite metadata; CORRUPT_FILE=known unreadable slide; UNUSABLE_SCAN=valid file unsuitable for teaching use; DUPLICATE_SLIDE=superseded by another slide.',
  `created_date` timestamp NULL DEFAULT current_timestamp(),
  `objective_magnifications` varchar(20) DEFAULT NULL COMMENT 'Objective magnifications identified for the slide from crawler-derived metadata and manual validation where required. Single-view slides typically contain a single value (e.g. 20x or 40x). Some multiview slides contain image views acquired at different objective magnifications. In these cases multiple values are stored (e.g. 20x;40x). This reflects historical scanning practice where selected regions of interest were occasionally scanned at higher magnification than other areas of the same slide.',
  PRIMARY KEY (`slide_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

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
  `species_id` int(11) NOT NULL AUTO_INCREMENT,
  `species_name` varchar(255) NOT NULL,
  `scientific_name` varchar(255) DEFAULT NULL,
  `active` tinyint(1) DEFAULT 1,
  `notes` text DEFAULT NULL,
  `canonical_species` varchar(255) DEFAULT NULL,
  `species_group` varchar(255) DEFAULT NULL,
  `normalisation_status` varchar(50) DEFAULT NULL,
  `also_known_as` text DEFAULT NULL,
  `review_status` varchar(50) DEFAULT NULL,
  `confidence` varchar(20) DEFAULT NULL,
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
  `setting_name` varchar(100) NOT NULL,
  `setting_value` text NOT NULL,
  `updated_by` varchar(100) DEFAULT NULL,
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`setting_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

DROP TABLE IF EXISTS `tissue_dictionary`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `tissue_dictionary` (
  `tissue_id` int(11) NOT NULL AUTO_INCREMENT,
  `tissue_name` varchar(255) NOT NULL,
  `tissue_category` varchar(255) DEFAULT NULL,
  `active` tinyint(1) DEFAULT 1,
  `notes` text DEFAULT NULL,
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
  `token_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `activation_token` char(36) NOT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `expires_at` timestamp NULL DEFAULT NULL,
  `used_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`token_id`),
  UNIQUE KEY `activation_token` (`activation_token`),
  KEY `fk_activation_user` (`user_id`),
  CONSTRAINT `fk_activation_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `user_id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `full_name` varchar(255) NOT NULL,
  `institution` varchar(255) DEFAULT NULL,
  `guid` varchar(64) DEFAULT NULL,
  `role` enum('user','admin','system_admin') NOT NULL DEFAULT 'user',
  `authentication_method` enum('LOCAL','LDAP') NOT NULL DEFAULT 'LOCAL',
  `account_status` enum('PENDING_ACTIVATION','ACTIVE','DISABLED') NOT NULL DEFAULT 'PENDING_ACTIVATION',
  `contributions_count` int(11) NOT NULL DEFAULT 0,
  `contributions_accepted_count` int(11) NOT NULL DEFAULT 0,
  `password_hash` text DEFAULT NULL,
  `approved_by` varchar(100) DEFAULT NULL,
  `approved_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `last_login_at` datetime DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;


SET FOREIGN_KEY_CHECKS=1;
