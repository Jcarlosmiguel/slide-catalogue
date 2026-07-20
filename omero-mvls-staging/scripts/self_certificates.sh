#!/bin/bash
set -euo pipefail

########################################
# What this is
########################################
# Bootstraps a self-signed certificate when there's no real IT-issued
# one yet (fresh/local/test deployments) - see SETUP.md. Writes to the
# exact same target files certificates.sh uses (fullchain.pem,
# omero.key, server.pem/.key/.p12, ffdhe2048.pem), so nginx.conf and
# extra.omero need zero changes regardless of which script populated
# them. Once IT provides a real cert, just run certificates.sh - it
# overwrites these in place.
#
# Deliberately a separate script from certificates.sh rather than a
# prompt inside it: certificates.sh is meant to be routinely re-run
# (renewals, cron) and stays fully non-interactive by design. Adding an
# interactive "generate a self-signed cert instead?" prompt there would
# either have to be suppressed on every automated run, or risk someone
# fat-fingering a production renewal into overwriting a real cert with
# a throwaway one.

########################################
# --dry-run / --force
########################################
# --dry-run: every mutating step prints what it would do instead of
# doing it, same convention as the other scripts here.
# --force: bypasses the real-certificate protection check below. Off by
# default on purpose - see that section.
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
# openssl is the only real external dependency - everything else here
# is core coreutils (mkdir/cp/chmod/chown), safe to assume present on
# any Linux host.
MISSING_DEPS=()
command -v openssl >/dev/null 2>&1 || MISSING_DEPS+=(openssl)

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo "Error: missing required command(s): ${MISSING_DEPS[*]}"
    echo "Install with your distro's package manager, e.g.:"
    echo "  Debian/Ubuntu: sudo apt install openssl"
    echo "  RHEL/Fedora:   sudo dnf install openssl"
    exit 1
fi

########################################
# Require root
########################################
# Needed for the final chown -R to UID/GID 1000, same reasoning as
# certificates.sh. Still required under --dry-run for an accurate
# preview of what the real run would do.
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: this script must be run with sudo."
    exit 1
fi

########################################
# Script location
########################################
# Lives in ./scripts/ alongside certificates.sh etc. - resolve
# .env/certs/nginx against this script's parent directory, not its own,
# so it works whether invoked as ./scripts/self_certificates.sh from the
# project root or as `cd scripts && ./self_certificates.sh`.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

########################################
# Load .env
########################################
ENV_FILE="$PROJECT_ROOT/.env"

if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "Error: Missing .env file"
    exit 1
fi

########################################
# Validate variables
########################################
# No CERTLOCATION/PEMLOCATION here - those are the IT-source paths
# certificates.sh needs; this script generates its own, it doesn't
# import one.
REQUIRED=(
  OMEROGLACIER2ICESSLPASSWORD
  FULLDOMAIN
  NGINXCERTIFICATEFOLDER
)

for v in "${REQUIRED[@]}"; do
    [ -z "${!v:-}" ] && { echo "Error: Missing $v"; exit 1; }
done

########################################
# Derive initial domain (same logic as certificates.sh, so filenames match)
########################################
INITIALDOMAINPART=${FULLDOMAIN%%.*}

# Best-effort second SAN entry from APP_BASE_URL (catalogue's domain),
# if it's set to something that looks like a real URL. Not required -
# falls back to FULLDOMAIN alone if unset, still a CHANGE_ME placeholder,
# or unparseable.
SAN_LIST="DNS:$FULLDOMAIN"
if [ -n "${APP_BASE_URL:-}" ] && [ "$APP_BASE_URL" != "CHANGE_ME" ]; then
    CATALOGUE_HOST=$(echo "$APP_BASE_URL" | sed -E 's#^https?://##; s#[:/].*##')
    if [ -n "$CATALOGUE_HOST" ] && [ "$CATALOGUE_HOST" != "$FULLDOMAIN" ]; then
        SAN_LIST="$SAN_LIST,DNS:$CATALOGUE_HOST"
    fi
fi

########################################
# Config
########################################
TARGET_UID=1000
TARGET_GID=1000

CERTS_ROOT="$PROJECT_ROOT/certs"
NGINX_CERTS_DIR="$CERTS_ROOT/nginx"
OMERO_DIR="$CERTS_ROOT/omero"

DEST_CERT="$NGINX_CERTS_DIR/fullchain.pem"
DEST_KEY="$NGINX_CERTS_DIR/${INITIALDOMAINPART}.key"

if $DRY_RUN; then
    echo "DRY RUN: would create directories if missing: $NGINX_CERTS_DIR $OMERO_DIR"
else
    sudo mkdir -p "$NGINX_CERTS_DIR" "$OMERO_DIR"
fi

########################################
# Protect any real certificate already in place
########################################
# A self-signed cert's Issuer and Subject are identical (it signed
# itself); a real CA-issued cert's are not. If DEST_CERT already exists
# and looks CA-issued, refuse to clobber it with a throwaway one -
# --force overrides.
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
        echo "Generating a throwaway self-signed cert would overwrite it."
        if $FORCE; then
            echo "--force given - proceeding anyway."
        else
            echo "Re-run with --force if you really mean to replace it."
            exit 1
        fi
        echo "############################################################"
    else
        echo "Existing $DEST_CERT looks self-signed already - safe to regenerate."
    fi
fi

########################################
# Generate self-signed cert + key
########################################
if $DRY_RUN; then
    echo "DRY RUN: would generate self-signed cert+key (365 days, SAN: $SAN_LIST):"
    echo "  $DEST_CERT"
    echo "  $DEST_KEY"
else
    echo "Generating self-signed certificate (SAN: $SAN_LIST)..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$DEST_KEY" \
        -out "$DEST_CERT" \
        -subj "/CN=$FULLDOMAIN" \
        -addext "subjectAltName=$SAN_LIST"

    sudo chmod 664 "$DEST_CERT"
    sudo chmod 600 "$DEST_KEY"
fi

########################################
# OMERO copy + rename (same layout certificates.sh produces)
########################################
OMERO_CERT="$OMERO_DIR/server.pem"
OMERO_KEY="$OMERO_DIR/server.key"

if $DRY_RUN; then
    echo "DRY RUN: would copy $DEST_CERT -> $OMERO_CERT (chmod 664)"
    echo "DRY RUN: would copy $DEST_KEY -> $OMERO_KEY (chmod 600)"
else
    cp "$DEST_CERT" "$OMERO_CERT"
    cp "$DEST_KEY" "$OMERO_KEY"

    chmod 664 "$OMERO_CERT"
    chmod 600 "$OMERO_KEY"
fi

########################################
# PKCS12
########################################
PKCS12="$OMERO_DIR/server.p12"

if $DRY_RUN; then
    echo "DRY RUN: would generate PKCS12 bundle (chmod 600): $PKCS12"
else
    openssl pkcs12 -export \
      -out "$PKCS12" \
      -in "$OMERO_CERT" \
      -inkey "$OMERO_KEY" \
      -passout pass:"$OMEROGLACIER2ICESSLPASSWORD"

    chmod 600 "$PKCS12"
fi

########################################
# DH parameters (reused if already present - not tied to a specific
# cert/key pair, safe to keep across regenerations, same as certificates.sh)
########################################
DHPARAM_OMERO="$OMERO_DIR/ffdhe2048.pem"
DHPARAM_NGINX="$NGINX_CERTS_DIR/ffdhe2048.pem"

if [ ! -f "$DHPARAM_OMERO" ]; then
    if $DRY_RUN; then
        echo "DRY RUN: would generate DH parameters (slow - real CPU work, skipped under --dry-run): $DHPARAM_OMERO"
    else
        echo "Generating DH parameters"
        openssl dhparam -out "$DHPARAM_OMERO" 2048
    fi
fi

if [ ! -f "$DHPARAM_NGINX" ]; then
    if $DRY_RUN; then
        echo "DRY RUN: would copy $DHPARAM_OMERO -> $DHPARAM_NGINX"
    else
        cp "$DHPARAM_OMERO" "$DHPARAM_NGINX"
    fi
fi

########################################
# Ownership
########################################
if $DRY_RUN; then
    echo "DRY RUN: would chown -R $TARGET_UID:$TARGET_GID $CERTS_ROOT"
else
    sudo chown -R "$TARGET_UID:$TARGET_GID" "$CERTS_ROOT"
fi

########################################
# Output
########################################
echo ""
if $DRY_RUN; then
    echo "DRY RUN complete - no changes were made."
else
    echo "Done - self-signed certificate generated."
    echo "Browsers will show a trust warning for this cert - expected for"
    echo "self-signed. Swap in a real one later by running certificates.sh"
    echo "once IT provides it; it overwrites these same files in place."
fi
echo "Certificates root: $CERTS_ROOT"
