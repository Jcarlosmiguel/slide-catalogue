# MVLS Catalogue Database

## Overview

The catalogue uses MariaDB for metadata storage and application
configuration.

Database:

```text
mvls_catalogue
```

---

# Core Catalogue Tables

## slides

Master slide inventory.

Contains:

- Slide identifiers
- File locations
- Core catalogue information

---

## slide_metadata

Primary descriptive metadata.

Examples:

- Organ
- Species
- Stain

---

## slide_technical_metadata

Technical whole-slide image metadata.

Examples:

- Dimensions
- Scanner information
- Objective magnification

---

# Annotation Tables

## slide_annotations

Teacher and workflow annotations.

---

## slide_david_annotations

David Jenkinson annotation linkage.

---

## slide_tissue_annotations

Tissue classification assignments.

---

# Dictionary Tables

## species_dictionary

Controlled species vocabulary.

---

## organ_dictionary

Controlled organ vocabulary.

---

## tissue_dictionary

Controlled tissue vocabulary.

---

## stain_dictionary

Controlled stain vocabulary.

---

## organ_tissue_dictionary

Relationship table linking organs and tissues.

---

# User Management Tables

## users

Application users.

---

## access_requests

Pending user access requests.

---

## user_activation_tokens

Account activation tokens.

---

## password_reset_tokens

Password reset tokens, emailed to users who request a reset via
"Forgot your password?" on the login page. One-time use, expire
2 hours after creation.

---

## password_reset_log

Admin-visible audit log of password reset activity: requests,
completions, and attempts against unknown emails or inactive
accounts. Not exposed in the admin UI - query directly.

---

# Feedback Tables

## slide_feedback

Feedback submissions.

---

## slide_feedback_actions

Administrative feedback actions.

Examples:

- Status changes
- Metadata updates

---

# Administrative Configuration

## system_settings

System configuration values.

Examples:

- Email settings
- Notification configuration

---

# Views

## v_slide_catalogue_app

Primary catalogue view.

---

## v_slide_david_notes

David Jenkinson annotation view.

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
