#!/bin/bash
set -euo pipefail

########################################
# What this is
########################################
# Generates a self-signed certificate for nginx.selfsigned.conf.example
# (Tier 2 in this folder's README.md) - for a standalone deployment with
# no real IT-issued certificate yet. Writes fullchain.pem/<domain>.key/
# ffdhe2048.pem to certs/nginx/ at the repo root, which is exactly what
# that nginx config expects to find mounted at /etc/nginx/ssl/.
#
# Adapted from an OMERO-integrated deployment's own equivalent script (a
# sibling deployment of this same catalogue, merged into an existing
# OMERO docker-compose stack) - dropped here:
# the OMERO-side PKCS12 bundle and OMEROGLACIER2ICESSLPASSWORD
# requirement (nothing here needs them, this is nginx-only), and the
# ACL grant for OMERO's fixed container UID (that workaround exists
# because OMERO's server process runs entirely as a non-root user;
# nginx's official image keeps its master process as root by default,
# which is what actually opens the certificate/key files, so a normal
# root-owned 600 key is already readable - no ACL trick needed here).
#
# Once you have a real certificate (e.g. Let's Encrypt), just replace
# the two files this script writes - nginx.selfsigned.conf.example's
# paths don't need to change either way.

########################################
# --dry-run / --force
########################################
DRY_RUN=false
FORCE=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --force) FORCE=true ;;
        *) echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done

########################################
# Dependency check
########################################
command -v openssl >/dev/null 2>&1 || {
    echo "Error: openssl is required."
    echo "  Debian/Ubuntu: sudo apt install openssl"
    echo "  RHEL/Fedora:   sudo dnf install openssl"
    exit 1
}

########################################
# Script location / project root
########################################
# This script lives in catalogue/docs/standalone/ - the repo root
# (where compose.yaml/.env live, and where certs/ gets created) is two
# levels up.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

########################################
# Load .env and derive the domain
########################################
# Reuses APP_BASE_URL (already a required setting for this catalogue -
# see the repo root .env.example) rather than introducing a whole new
# variable just for this script. Falls back to prompting if it's unset
# or still a placeholder.
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

DOMAIN=""
if [ -n "${APP_BASE_URL:-}" ] && [ "$APP_BASE_URL" != "CHANGE_ME" ]; then
    DOMAIN=$(echo "$APP_BASE_URL" | sed -E 's#^https?://##; s#[:/].*##')
fi

if [ -z "$DOMAIN" ]; then
    read -rp "Domain for this certificate (e.g. catalogue.yourdomain.com, or localhost for local testing): " DOMAIN
fi

if [ -z "$DOMAIN" ]; then
    echo "Error: no domain given and APP_BASE_URL isn't set in $ENV_FILE."
    exit 1
fi

########################################
# Output paths
########################################
CERTS_DIR="$PROJECT_ROOT/certs/nginx"
DEST_CERT="$CERTS_DIR/fullchain.pem"
DEST_KEY="$CERTS_DIR/${DOMAIN}.key"
DHPARAM="$CERTS_DIR/ffdhe2048.pem"

if $DRY_RUN; then
    echo "DRY RUN: would create directory if missing: $CERTS_DIR"
else
    mkdir -p "$CERTS_DIR"
fi

########################################
# Protect any real certificate already in place
########################################
# A self-signed cert's Issuer and Subject are identical (it signed
# itself); a real CA-issued cert's are not. Refuse to clobber a
# real one with a throwaway self-signed one unless --force is given.
if [ -f "$DEST_CERT" ]; then
    EXISTING_ISSUER=$(openssl x509 -in "$DEST_CERT" -noout -issuer 2>/dev/null || true)
    EXISTING_SUBJECT=$(openssl x509 -in "$DEST_CERT" -noout -subject 2>/dev/null || true)

    if [ -n "$EXISTING_ISSUER" ] && [ "${EXISTING_ISSUER#issuer=}" != "${EXISTING_SUBJECT#subject=}" ]; then
        echo "############################################################"
        echo "# REFUSING TO OVERWRITE: $DEST_CERT"
        echo "############################################################"
        echo "This looks like a real, CA-issued certificate, not a"
        echo "self-signed one:"
        echo "  $EXISTING_ISSUER"
        echo "  ${EXISTING_SUBJECT/subject/ subject}"
        echo
        if $FORCE; then
            echo "--force given - proceeding anyway."
        else
            echo "Re-run with --force if you really mean to replace it."
            exit 1
        fi
    else
        echo "Existing $DEST_CERT looks self-signed already - safe to regenerate."
    fi
fi

########################################
# Generate self-signed cert + key
########################################
if $DRY_RUN; then
    echo "DRY RUN: would generate self-signed cert+key (365 days, CN=$DOMAIN):"
    echo "  $DEST_CERT"
    echo "  $DEST_KEY"
else
    echo "Generating self-signed certificate for $DOMAIN ..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$DEST_KEY" \
        -out "$DEST_CERT" \
        -subj "/CN=$DOMAIN" \
        -addext "subjectAltName=DNS:$DOMAIN"

    # 644 for the cert (nginx serves its contents to every visitor
    # anyway, no secrecy to protect); 600 for the key. nginx's official
    # image runs its master process as root by default (only the worker
    # processes drop to an unprivileged user), and the master process is
    # what opens this file before workers fork - so a root-owned 600 key
    # is already readable without any extra ACL/ownership steps, as long
    # as compose.yaml doesn't override catalogue_nginx's default user.
    chmod 644 "$DEST_CERT"
    chmod 600 "$DEST_KEY"
fi

########################################
# DH parameters
########################################
# Slow to generate (real CPU work), not tied to any specific cert/key
# pair - reused across regenerations rather than recreated every time.
if [ ! -f "$DHPARAM" ]; then
    if $DRY_RUN; then
        echo "DRY RUN: would generate DH parameters (slow, skipped under --dry-run): $DHPARAM"
    else
        echo "Generating DH parameters (this takes a while) ..."
        openssl dhparam -out "$DHPARAM" 2048
    fi
fi

########################################
# Output
########################################
echo ""
if $DRY_RUN; then
    echo "DRY RUN complete - no changes were made."
else
    echo "Done - self-signed certificate generated for $DOMAIN."
    echo "Browsers will show a trust warning for this cert - expected for"
    echo "self-signed. Swap in a real one later by replacing $DEST_CERT"
    echo "and $DEST_KEY in place; nginx.selfsigned.conf.example's paths"
    echo "don't need to change."
fi
echo "Certificate directory: $CERTS_DIR"
