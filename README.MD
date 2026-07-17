# MVLS Virtual Microscopy Catalogue

## Overview

The MVLS Virtual Microscopy Catalogue is a web-based catalogue for the
University of Glasgow College of Medical, Veterinary and Life Sciences
(MVLS) Virtual Microscopy Archive.

The system allows users to:

- Search virtual microscopy slides.
- Review catalogue metadata.
- Access David Jenkinson annotations.
- Submit metadata and annotation feedback.
- Request access to restricted resources.
- Browse documentation and workflow guidance.
- Locate slide storage locations and associated resources.

The catalogue is designed to support teaching staff, demonstrators,
course organisers, and archive curators.

---

# Architecture

## Components

### Frontend

Static HTML, CSS and JavaScript delivered by NGINX.

Location:

```text
frontend/
```

### Backend

FastAPI application providing:

- Authentication
- Search
- Feedback handling
- Access request processing
- Administrative functions
- System settings

Location:

```text
backend/
```

### Database

MariaDB database containing:

- Slide metadata
- Technical metadata
- Dictionary tables
- User accounts
- Access requests
- Feedback records
- Administrative settings

### Reverse Proxy

NGINX provides:

- Static content delivery
- Backend proxying
- Document serving
- Thumbnail serving

Location:

```text
nginx/
```

---

# Docker Deployment

Services:

```text
catalogue_mariadb
catalogue_backend
catalogue_nginx
adminer
```

Start the system:

```bash
docker compose up -d
```

Stop the system:

```bash
docker compose down
```

View logs:

```bash
docker compose logs
```

---

# Project Structure

```text
backend/
db/
docs/
documents/
frontend/
nginx/
```

## Key Directories

### Documents

User-facing documentation.

```text
documents/
```

### Documentation

Project documentation and maintenance notes.

```text
docs/
```

### Thumbnails

Generated catalogue thumbnails.

```text
thumbnails/
```

### Manual Thumbnails

Temporary staging area for manually generated or curated thumbnails.

```text
manual_thumbnails/
```

### Thumbnail Backups

Automatic backups generated during thumbnail replacement.

```text
thumbnail_backups/
```

---

# User Roles

## User

Can:

- Search slides
- View metadata
- Submit feedback
- View documentation

## Administrator

Can additionally:

- Review feedback
- Process access requests
- Manage system settings

---

# Thumbnail Workflow

Thumbnail generation uses a two-stage process.

```text
Slides
   ↓
generate_2048_png_thumbnails.py
   ↓
manual_thumbnails/
   ↓
sync_manual_thumbnails.py
   ↓
thumbnails/2048
thumbnails/1024
thumbnails/512
```

See:

```text
docs/thumbnail-maintenance.md
```

for full details.

---

# Authentication

The system supports local catalogue authentication.

Guest users can access public information.

Protected pages require login.

Administrative pages require administrator privileges.

---

# Database Backups

Database backups are stored separately from the application source code.

Typical backup locations:

```text
backups/database/
```

---

# Source Control

Git is used for source control.

Generated files are intentionally excluded from version control:

```text
thumbnails/
manual_thumbnails/
thumbnail_backups/
backups/
```

Only source code, configuration and documentation are tracked.

---

# Development Notes

The project is under active development.

Current areas of focus include:

- Administrative interface normalisation
- Documentation improvements
- Thumbnail management workflow
- User account management
- Notification management

---

# Licence

University of Glasgow MVLS Internal Project.

Not intended for public redistribution.
