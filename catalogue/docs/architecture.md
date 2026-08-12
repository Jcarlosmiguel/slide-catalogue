# Catalogue Architecture

## Overview

The Virtual Microscopy Catalogue provides a searchable catalogue of
virtual microscopy slides and associated metadata.

The application is designed to support:

- Teaching staff
- Demonstrators
- Course organisers
- Catalogue administrators
- Archive curators

This app is fully standalone and doesn't require OMERO. It was originally
built to run alongside an OMERO deployment, sharing one nginx/public IP
and routed by domain, with each app's own database kept fully
independent. See `docs/omero-integration/` for sanitized example
`compose.yaml`/`.env`/`nginx.conf` files and a step-by-step guide if you
want to run it the same way.

## Relationship to OMERO

The catalogue is not a replacement for OMERO, and importing every
cataloged slide into OMERO is neither expected nor usually desirable -
the two serve different purposes:

- **The catalogue indexes the full collection.** Thumbnails, search,
  metadata, and annotation all work directly against the raw slide files
  on the archive share - no OMERO import required. This is what makes it
  practical to catalogue an entire historical archive (potentially
  thousands of slides going back decades) without every one of them
  needing to go through OMERO's own processing first.
- **OMERO hosts the currently-teaching-relevant subset.** OMERO's
  pyramidal tile processing is what makes real-time pan/zoom/annotation
  viewing possible, but it's genuinely expensive in storage - importing
  the entire archive would multiply storage needs many times over for
  slides nobody is actively using. Promoting a slide from "cataloged" to
  "viewable in OMERO" is a deliberate curatorial decision, not an
  automatic sync: export it (typically via QuPath - see
  `documents/prepare-slides.html` and `documents/omero-import.html` for
  the walkthrough) and import it through OMERO.insight.

There is deliberately no automated link between a catalogue slide row
and an OMERO image ID - the decision of what's worth promoting to OMERO
is a human one, made slide by slide, not something this app tracks or
drives. This also means the archive itself can stay on read-only
storage: the catalogue never needs to write to it, only OMERO's own
import step does, and only for the slides actually being promoted.

---

# High-Level Architecture

```text
                 Browser
                     |
                     v

                 NGINX
                     |
        +------------+------------+
        |                         |
        v                         v

  Static Frontend          FastAPI Backend

                                |
                                v

                           MariaDB

                                |
                                v

                       Slide Storage
```

---

# Components

## Frontend

Technology:

- HTML
- CSS
- JavaScript

Responsibilities:

- Search interface
- Slide display
- Documentation
- Feedback submission
- Access request submission

Location:

```text
frontend/
```

---

## Backend

Technology:

- FastAPI
- Python

Responsibilities:

- Authentication
- Database access
- Searches
- Feedback and correction handling (metadata corrections, reported
  annotation errors, expert-note corrections)
- Access requests
- QuPath annotation script generation
- Administration

Location:

```text
backend/
```

---

## Database

Technology:

- MariaDB

Responsibilities:

- Slide metadata
- Technical metadata
- Dictionary tables
- User accounts
- System configuration

---

## NGINX

Responsibilities:

- Static file delivery
- Backend proxying
- Document hosting
- Thumbnail hosting

Location:

```text
nginx/
```

---

# Authentication Model

## Public

Accessible without login.

Examples:

- Home
- About
- Contact

---

## Protected

Requires authentication.

Examples:

- Documentation
- Internal workflow guidance

---

## Reviewer / Expert

Requires the `reviewer_expert` role, authorized per-permission via
`role_permissions` rather than hardcoded role checks (see
`app/permissions.py`). Roles are DB-assigned, not self-service.

Examples:

- Reviewer dashboard - review and act on submitted corrections
  (`reviewer-dashboard.html`), cannot approve a correction they submitted
  themselves
- Annotation error review (`annotation-review.html`)
- Expert-authored slide notes and legacy contributor note editing

---

## Administrative

Requires administrator privileges (`admin` or `system_admin`;
`system_admin` is full-access and DB-assignable only).

Examples:

- Corrections Management
- Site Feedback
- User Management
- Access Requests
- Blocked Access Requests
- Password Reset Log
- System Settings
