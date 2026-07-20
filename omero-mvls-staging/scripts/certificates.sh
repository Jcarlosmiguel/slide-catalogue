#!/bin/bash
set -euo pipefail

########################################
# Modified for the catalogue merge
########################################
# This replaces omero-mvls/certificates.sh. The only functional change:
# the old script could regenerate nginx.conf from a hardcoded heredoc
# template that only knew about a single $FULLDOMAIN and had no idea
# about the catalogue server block, the CORS/Ajax headers, or the
# /images/ logo location - answering "y" to its overwrite prompt would
# silently revert nginx.conf to omero-only. See
# catalogue/docs/merge-into-omero-mvls/RUNBOOK.md ("OPEN ITEMS") for the
# full explanation.
#
# Everything else (copying the IT-renewed cert/key, the OMERO
# server.pem/server.key/server.p12 repackaging, DH params) is untouched
# and still runs exactly as before - that part is safe and still needed
# on every renewal.
########################################

########################################
# --dry-run
########################################
# Every mutating step below (mkdir, copy, chmod, chown, DH param
# generation, PKCS12 export, README creation) is gated on this. The
# validation/verification steps still run for real - they're read-only
# and an accurate preview needs them. DH param generation is the
# slowest step by far (real CPU work); dry-run skips it entirely rather
# than doing it "for preview" and throwing the result away.
DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        *) echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done

########################################
# Require root
########################################
# This script always needs to run via sudo - it reads a root-only
# private key path and writes root-owned destinations. Some commands
# below are individually sudo-prefixed and some aren't (carried over
# from the original script); without this check, running it unprivileged
# wouldn't fail cleanly - the sudo-prefixed lines would still work (each
# prompting on its own) while the plain ones silently ran as the
# invoking user instead, leaving a mix of root-owned and user-owned
# output files. Fail fast instead. (Still required under --dry-run too,
# since reading PEMLOCATION - a root-only private key path - needs root
# either way, and the point of a dry run is an accurate preview of what
# the real run would do.)
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: this script must be run with sudo."
    exit 1
fi

########################################
# Script location
########################################
# Lives in ./scripts/ alongside backup_omero.sh etc. - one level below
# .env/certs/nginx, so everything below resolves against PROJECT_ROOT
# (this script's parent directory), not SCRIPT_DIR itself. Works
# whether invoked as ./scripts/certificates.sh from the project root or
# as `cd scripts && ./certificates.sh`.
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
# NGINX_PORT_GENERAL / NGINX_PORT_SECURE dropped from this list - they
# were only used by the nginx.conf heredoc removed below. PERMISSIONS
# also dropped - certificate file mode is now hardcoded below (664,
# same value as before) since it never varied in practice; safe to
# remove PERMISSIONS from .env entirely.
REQUIRED=(
  CERTLOCATION
  PEMLOCATION
  OMEROGLACIER2ICESSLPASSWORD
  FULLDOMAIN
  NGINXCERTIFICATEFOLDER
)

for v in "${REQUIRED[@]}"; do
    [ -z "${!v:-}" ] && { echo "Error: Missing $v"; exit 1; }
done

[ -f "$CERTLOCATION" ] || { echo "Error: Missing cert: $CERTLOCATION"; exit 1; }
[ -f "$PEMLOCATION" ]  || { echo "Error: Missing key: $PEMLOCATION"; exit 1; }
echo "Found certificate (CERTLOCATION): $CERTLOCATION"
echo "Found key (PEMLOCATION): $PEMLOCATION"

########################################
# Derive initial domain
########################################
INITIALDOMAINPART=${FULLDOMAIN%%.*}

########################################
# Config
########################################
TARGET_UID=1000
TARGET_GID=1000

CERTS_ROOT="$PROJECT_ROOT/certs"
NGINX_CERTS_DIR="$CERTS_ROOT/nginx"
OMERO_DIR="$CERTS_ROOT/omero"

NGINX_CONFIG_DIR="$PROJECT_ROOT/nginx"

if $DRY_RUN; then
    echo "DRY RUN: would create directories if missing: $NGINX_CERTS_DIR $OMERO_DIR $NGINX_CONFIG_DIR"
else
    sudo mkdir -p "$NGINX_CERTS_DIR" "$OMERO_DIR" "$NGINX_CONFIG_DIR"
fi

########################################
# Copy helper
########################################
copy_if_changed() {
    local SRC="$1"
    local DEST="$2"

    if [ -f "$DEST" ] && cmp -s "$SRC" "$DEST"; then
        echo "No change: $DEST"
        COPY_CHANGED=false
    elif $DRY_RUN; then
        if [ -f "$DEST" ]; then
            echo "DRY RUN: would update: $DEST"
        else
            echo "DRY RUN: would create: $DEST"
        fi
        COPY_CHANGED=true
    else
        echo "Copying: $DEST"
        sudo cp "$SRC" "$DEST"
        COPY_CHANGED=true
    fi
}

########################################
# Copy cert & key
########################################
CERT_FILE=$(basename "$CERTLOCATION")

DEST_CERT="$NGINX_CERTS_DIR/$CERT_FILE"
DEST_KEY="$NGINX_CERTS_DIR/${INITIALDOMAINPART}.key"

copy_if_changed "$CERTLOCATION" "$DEST_CERT"
CERT_CHANGED=$COPY_CHANGED
copy_if_changed "$PEMLOCATION" "$DEST_KEY"
KEY_CHANGED=$COPY_CHANGED

########################################
# Renewal summary - unambiguous answer to "is this actually a renewal,
# or am I already up to date?" Same logic runs under --dry-run (it's
# the comparison in copy_if_changed above, not the copy itself, that
# detects this), so this is accurate whether or not anything actually
# gets written.
########################################
echo ""
echo "############################################################"
if $CERT_CHANGED || $KEY_CHANGED; then
    if $DRY_RUN; then
        echo "# RENEWAL DETECTED (dry run) - cert and/or key in CERTLOCATION/"
        echo "# PEMLOCATION differ from what's currently in $NGINX_CERTS_DIR"
    else
        echo "# RENEWAL APPLIED - cert and/or key were updated in"
        echo "# $NGINX_CERTS_DIR"
    fi
else
    echo "# UP TO DATE - cert and key in CERTLOCATION/PEMLOCATION are"
    echo "# identical to what's already deployed in $NGINX_CERTS_DIR."
    echo "# Nothing to update."
fi
echo "############################################################"
echo ""

########################################
# Verify match
########################################
# Under --dry-run, DEST_CERT/DEST_KEY may not exist yet (nothing was
# actually copied above) - fall back to verifying the SOURCE files
# directly in that case, since that's what would end up being copied.
if $DRY_RUN && { [ ! -f "$DEST_CERT" ] || [ ! -f "$DEST_KEY" ]; }; then
    echo "DRY RUN: destination not yet created - verifying source cert/key instead"
    VERIFY_CERT="$CERTLOCATION"
    VERIFY_KEY="$PEMLOCATION"
else
    VERIFY_CERT="$DEST_CERT"
    VERIFY_KEY="$DEST_KEY"
fi

CERT_HASH=$(openssl x509 -noout -modulus -in "$VERIFY_CERT" | openssl md5)
KEY_HASH=$(openssl rsa -noout -modulus -in "$VERIFY_KEY" 2>/dev/null | openssl md5)

if [ "$CERT_HASH" != "$KEY_HASH" ]; then
    echo "Error: certificate and key do not match"
    exit 1
fi

echo "Certificate and key match"

# Reminder, since one SAN cert now covers both omero.mvls.gla.ac.uk and
# catalogue.mvls.gla.ac.uk - if this ever fails after a renewal, check
# with IT that the renewed cert's SAN list still includes both names.
if ! openssl x509 -in "$VERIFY_CERT" -noout -ext subjectAltName 2>/dev/null | grep -q "catalogue"; then
    echo "Warning: renewed certificate's SAN list does not appear to include a 'catalogue' domain - confirm with IT before this renewal goes live."
fi

########################################
# Permissions
########################################
if $DRY_RUN; then
    echo "DRY RUN: would chmod 664 $DEST_CERT, chmod 600 $DEST_KEY"
else
    sudo chmod 664 "$DEST_CERT"
    sudo chmod 600 "$DEST_KEY"
fi

########################################
# OMERO copy + rename
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

    # server.p12 embeds the private key (password-protected by
    # OMEROGLACIER2ICESSLPASSWORD) - explicit chmod so its permissions
    # don't depend on whatever umask happens to be active, same
    # treatment as server.key/omero.key above.
    chmod 600 "$PKCS12"
fi

########################################
# DH parameters
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
# Ownership (cert folders)
########################################
if $DRY_RUN; then
    echo "DRY RUN: would chown -R $TARGET_UID:$TARGET_GID $CERTS_ROOT"
else
    sudo chown -R "$TARGET_UID:$TARGET_GID" "$CERTS_ROOT"
fi

########################################
# nginx config folder ownership
########################################
if $DRY_RUN; then
    echo "DRY RUN: would chown -R $TARGET_UID:$TARGET_GID $NGINX_CONFIG_DIR"
else
    sudo chown -R "$TARGET_UID:$TARGET_GID" "$NGINX_CONFIG_DIR"
fi

########################################
# nginx.conf is no longer generated here
########################################
# Since the catalogue merge, nginx.conf is a hand-maintained file
# (tracked in git, covers both omero.mvls.gla.ac.uk and
# catalogue.mvls.gla.ac.uk, plus CORS/Ajax headers and the /images/ logo
# location). Auto-regenerating it from a template would silently drop
# all of that. This script now only refreshes certs/keys - if
# nginx.conf itself ever needs to change (new domain, new port), edit it
# directly and review with `git diff` / `nginx -t` before restarting.
echo ""
echo "nginx.conf was NOT touched by this script (by design - see comment"
echo "above). Only certs/keys were refreshed."

########################################
# README
########################################
README="$CERTS_ROOT/README.md"

if [ ! -f "$README" ]; then
    if $DRY_RUN; then
        echo "DRY RUN: would create $README"
    else
cat > "$README" <<EOF
TLS setup using Docker mounted folders.

Nginx:
- certificates in /etc/nginx/ssl
- config: /etc/nginx/nginx.conf (hand-maintained since the catalogue
  merge - not generated by this script, see comment in certificates.sh)
- host config folder: ./nginx

OMERO:
- certificates in /etc/ssl/omero
- config: /opt/omero/server/config/extra.omero

Restart containers after updating certificates:
  docker compose up -d nginx omeroserver
EOF
    fi
fi

########################################
# Output
########################################
echo ""
if $DRY_RUN; then
    echo "DRY RUN complete - no changes were made."
else
    echo "Done"
fi
echo "Certificates root: $CERTS_ROOT"
echo "Nginx config folder: $NGINX_CONFIG_DIR"
