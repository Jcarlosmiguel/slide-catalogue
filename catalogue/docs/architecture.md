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

Requires the `reviewer` or `expert` role, authorized per-permission via
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
