# Catalogue Database

## Overview

The catalogue uses MariaDB for metadata storage and application
configuration.

Database:

```text
catalogue
```

Schema setup: `backend/migrations/0000_initial_schema.sql` creates every
table and view below on a fresh database; `backend/migrations/000N_*.sql`
apply incrementally after that. Run both via
`backend/migrations/run_migrations.sh` - see that script's own header
comment for usage. Every table and column in the schema carries a SQL
`COMMENT` describing its purpose; the descriptions below are drawn from
those comments.

---

# Core Catalogue Tables

## slides

Core catalogue record for one virtual slide file - one row per slide,
joined by `slide_id` to `slide_metadata`, `slide_technical_metadata`,
`slide_annotations`, and the various correction/feedback tables.

Contains:

- Slide identifiers
- File locations
- Core catalogue information

---

## slide_metadata

Curated organ/species/stain/description metadata and generated thumbnail
paths for a slide - one row per `slide_id`, distinct from the raw
crawler-derived data in `slide_technical_metadata`.

Examples:

- Organ
- Species
- Stain

---

## slide_technical_metadata

Technical metadata extracted from virtual slide files during crawler
operations. The crawler uses both OpenSlide and TiffSlide to interrogate
slide files and extract scanner, acquisition, calibration and
image-structure metadata. This table preserves crawler-derived metadata
that is not part of the curated catalogue metadata model but may be
required for provenance, validation, image calibration, quality
assurance, future migrations and recrawling activities. Future crawler
runs should update represented fields in this table rather than adding
crawler-derived metadata directly to `slides`, `slide_metadata` or
`slide_annotations` unless the field becomes part of the authoritative
catalogue metadata model.

Examples:

- Dimensions
- Scanner information
- Objective magnification

---

# Annotation Tables

## slide_annotations

Region/point/line annotations attached to a slide - imported from an
external source system (`source_annotation_id` preserves the original
identifier from that system), or created directly by the app going
forward. `flagged_incorrect` is set
automatically when an accepted correction reports the annotation as
incorrect, and excludes it from the slide detail view (see
`slide_corrections` below).

---

## slide_tissue_annotations

Permanent curated table linking slides to canonical tissues or
histological structures.

---

# Legacy Curation Tables

Historical curation data reconciling an earlier, external archive of
notes and keywords against catalogue slides. Distinct from
`slide_expert_notes` (new notes written directly by reviewer/expert-role
users) - see the "Reviewer/Expert System" section below.

## legacy_curation

Curated legacy contributor annotation records and note text linked to
slides through `slide_legacy_curation_links`. Experts can edit
`annotation_title`/`note_text` directly via `PATCH /api/legacy-notes/
{curation_id}` - every edit is captured in `legacy_curation_edit_history`
first, so nothing is silently lost if a change turns out to be wrong.

## legacy_curation_edit_history

Audit trail of every edit an expert makes to a `legacy_curation` note -
preserves the prior title/text before each overwrite.

## slide_legacy_curation_links

Reconciliation layer linking slides to preserved legacy archive records.
Source annotations remain in `legacy_curation` and are referenced through
`legacy_curation_id` for provenance preservation. Queried live by the app
via the `v_slide_legacy_notes` view (see "Views" below).

## legacy_curation_slide_links

Reconciliation candidates/links between `legacy_curation` records and
catalogue slides - a broader or earlier-stage table than the confirmed
`slide_legacy_curation_links`.

## legacy_curation_match_stage

Staging table for many-to-many matching of legacy contributor records to
`slide_id` values. Only approved rows should be inserted into
`slide_legacy_curation_links`.

---

# Reviewer/Expert System

## role_permissions

Maps each role (`reviewer`, `expert`, etc.) to the permission keys it
grants - drives `require_permission()` authorization checks for
reviewer/expert capabilities, without hardcoding role names in
application code.

## slide_expert_notes

Notes written directly by expert-role users on a slide, shown in the
"Expert contributor notes" section alongside (but separate from) the
read-only legacy contributor import (see `legacy_curation` above).

---

# Dictionary Tables

## species_dictionary

Controlled vocabulary for species associated with slides, annotations and
reconciliation workflows.

## organ_dictionary

Permanent dictionary of canonical anatomical organs and anatomical
structures used to normalise `slide_metadata.organ`.

## tissue_dictionary

Permanent dictionary of canonical tissues, histological tissue classes,
and microscopic anatomical structures.

## stain_dictionary

Curated stain normalisation dictionary. Maps original stain strings found
in `slide_metadata.stain`, filenames, and legacy sources to canonical
stain terminology while preserving aliases, historical names, composite
stains, review status, confidence, and explanatory notes.

## organ_tissue_dictionary

Permanent bridge table describing curated relationships between canonical
organs and canonical tissues.

---

# Curation Staging Tables

Temporary/working tables used during data cleanup, not part of the
steady-state catalogue model.

## duplicate_slide_mapping

Temporary curation table for suspected or confirmed duplicate slide
mappings.

## slides_to_be_deleted_review

Temporary curation table listing slides proposed for deletion or
exclusion.

## annotation_contributors

Reference list of individuals credited as annotation contributors/authors
in imported source data, for display and attribution.

---

# User Management Tables

## users

Catalogue user accounts - local or LDAP-authenticated, with a role
controlling what they can see and do (see `role_permissions` for
reviewer/expert capabilities). `last_login_at` is updated on every
successful login.

## access_requests

Self-service requests for catalogue access, reviewed by an admin before a
user account is created.

## access_request_blocked_attempts

Log of access requests rejected automatically before reaching the review
queue (e.g. duplicate email already registered), kept for abuse
monitoring.

## user_activation_tokens

Single-use, time-limited tokens issued to newly-approved accounts to set
their initial password and activate.

## password_reset_tokens

Single-use, time-limited tokens issued for the forgot-password flow.
Emailed to users who request a reset via "Forgot your password?" on the
login page. Expire 2 hours after creation.

## password_reset_log

Audit log of password-reset attempts, successful or not, for abuse
monitoring and support troubleshooting. Not exposed in the admin UI -
query directly.

---

# Feedback Tables

## slide_corrections

User-submitted feedback/correction reports awaiting admin or reviewer
action - covers metadata corrections, reported annotation errors, and
expert-note corrections, distinguished by `feedback_source`
(`metadata` / `slide_annotation` / `legacy_note`). A reviewer cannot
approve a correction they submitted themselves. Accepting a
`slide_annotation`-sourced report reporting an annotation as incorrect
sets `slide_annotations.flagged_incorrect` automatically (reversibly, if
later reopened).

## slide_correction_actions

Append-only audit log of actions taken against a `slide_corrections` row
- one row per status change or applied metadata update.

## site_feedback

General free-text feedback about the catalogue site/UX, not tied to a
specific slide or correction - distinct from `slide_corrections`.

---

# Administrative Configuration

## system_settings

Simple key-value store for admin-configurable application settings.

Examples:

- Email settings
- Notification configuration

---

# Migration Tracking

## schema_migrations

Tracks which `migrations/*.sql` files have already been applied, so
`run_migrations.sh` only ever applies each one once. Created
automatically by `run_migrations.sh` itself - not part of any numbered
migration file.

---

# Views

## v_slide_catalogue_app

Flattened slide + metadata + canonical-stain view, joining `slides`,
`slide_metadata`, and `stain_dictionary`. Not queried by the app itself -
kept for ad-hoc reporting/Adminer use.

## v_slide_legacy_notes

Joins `slide_legacy_curation_links` to `slides` and `legacy_curation` to
surface each slide's legacy contributor note(s). Queried live by
`get_slide` and `search_slides` in `main.py`.

---

# Backup Strategy

Full database backups:

```text
backups/database/full/
```

Archive table backups:

```text
backups/database/archive-tables/
```
