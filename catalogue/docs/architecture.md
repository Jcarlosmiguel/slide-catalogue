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
- Feedback handling
- Access requests
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

## Administrative

Requires administrator privileges.

Examples:

- Feedback Management
- Access Requests
- System Settings
