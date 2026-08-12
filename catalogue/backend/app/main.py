import os
import json
import csv
import io
import re
import hmac
import time
import base64
import uuid
import zipfile

import hashlib
from datetime import (
    date,
    datetime,
    timedelta,
)
from argon2 import PasswordHasher
from decimal import Decimal
from typing import Any, Optional
from pydantic import BaseModel, Field
import pymysql
from fastapi import FastAPI, HTTPException, Query, Request, Response, Body, Depends
from fastapi.responses import StreamingResponse

from app.admin_audit import log_admin_action
from app.admin_sql import validate_statement
from app.backup_catalogue import create_backup
from app.sync_manual_thumbnails import sync as sync_manual_thumbnails
from app.sync_cmp_flags import sync as sync_cmp_flags
from app.cleanup_backups import cleanup as cleanup_backups
from app.mailer import send_email
from app.permissions import require_permission
from app.annotation_ome_xml import build_ome_xml
from app.annotation_ome_xml import parse_color as parse_annotation_color
from app.annotation_ome_xml import parse_arrow_style as parse_annotation_arrow_style
from app.annotation_ome_xml import slugify_filename_hint
from app.annotation_ome_xml import arrow_style_filename_label
from app.annotation_ome_xml import DEFAULT_COLOR_RGB as DEFAULT_ANNOTATION_COLOR
from app.annotation_ome_xml import DEFAULT_ARROW_STYLE as DEFAULT_ANNOTATION_ARROW_STYLE


app = FastAPI(
    title="Virtual Microscopy Catalogue API",
    root_path=os.getenv("APP_ROOT_PATH", "")
)

# ---------------------------------------------------------------------
# Prototype local authentication
# ---------------------------------------------------------------------

SESSION_COOKIE_NAME = "vmc_session"
SESSION_DURATION_SECONDS = 12 * 60 * 60


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


_KNOWN_PLACEHOLDER_SESSION_SECRETS = {
    "replace-this-with-a-long-random-secret",
    "change-me-to-a-long-random-string",
}


def get_session_secret() -> str:
    """Fails closed rather than falling back to a hardcoded default - this
    is a public template repo, so a hardcoded fallback secret here would
    let anyone who's read the source code forge a valid session (including
    role: system_admin) against any deployment that forgot to set this.
    Also rejects known placeholder values outright (e.g. .env.example's own
    "change-me-..." text) even though they're long enough to pass the
    length check - a shared, publicly-known placeholder is exactly as
    guessable as no secret at all if someone copies it verbatim."""
    secret = os.getenv("APP_SESSION_SECRET")
    if not secret or len(secret) < 32 or secret in _KNOWN_PLACEHOLDER_SESSION_SECRETS:
        raise RuntimeError(
            "APP_SESSION_SECRET must be set to a real, random string of at "
            "least 32 characters - e.g. `openssl rand -hex 32` - refusing "
            "to start with no secret or a known placeholder value."
        )
    return secret


def sign_payload(payload: dict) -> str:
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(
        get_session_secret().encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return body + "." + _b64url_encode(sig)


def verify_token(token):
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(
            get_session_secret().encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        provided = _b64url_decode(sig)

        if not hmac.compare_digest(expected, provided):
            return None

        payload = json.loads(_b64url_decode(body).decode("utf-8"))

        if payload.get("exp", 0) < int(time.time()):
            return None

        return payload

    except Exception:
        return None

password_hasher = PasswordHasher()


def require_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE_NAME)

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = verify_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return payload


def get_optional_user(request: Request):
    """Like require_user, but returns None instead of raising when there's
    no valid session - for endpoints usable by anonymous visitors that
    still want to attribute a submission to a logged-in user when one
    exists (e.g. site feedback)."""
    token = request.cookies.get(SESSION_COOKIE_NAME)

    if not token:
        return None

    return verify_token(token)



def require_admin(user: dict = Depends(require_user)):

    if user.get("role") not in (
        "admin",
        "system_admin",
    ):

        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return user


def require_system_admin(user: dict = Depends(require_user)):

    if user.get("role") != "system_admin":

        raise HTTPException(
            status_code=403,
            detail="System administrator access required"
        )

    return user

@app.post("/api/login")
def login(response: Response, payload: dict = Body(...)):
    """Authenticate by username, email, or GUID + password. Rejects
    non-ACTIVE accounts. Sets a signed session cookie and updates
    last_login_at on success. A wrong password when matched by GUID gets
    a more specific message - see the comment further down."""
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))

    conn = get_db_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    user_id,
                    username,
                    email,
                    guid,
                    full_name,
                    role,
                    account_status,
                    password_hash
                FROM users
                WHERE
                    username = %s
                    OR email = %s
                    OR guid = %s
                """,
                (
                    username,
                    username,
                    username
                )
            )

            candidates = cur.fetchall()

        if not candidates:

            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )

        if len(candidates) > 1:
            # username/email/guid aren't enforced as one shared unique
            # namespace at the DB level - if user A's username happens to
            # equal user B's email or guid (e.g. after a profile edit via
            # PUT /api/me/profile, which lets a user pick their own
            # username/guid), which row authenticates would otherwise be
            # whatever order MariaDB happens to return them in. Refuse
            # rather than pick one arbitrarily.
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )

        user = candidates[0]

        if user["account_status"] != "ACTIVE":

            raise HTTPException(
                status_code=401,
                detail="Account not active"
            )

        try:

            password_hasher.verify(
                user["password_hash"],
                password
            )

        except Exception:

            # A wrong password on an account matched by its GUID is worth a
            # more specific message: this catalogue has no live LDAP
            # integration yet (authentication_method is always LOCAL today,
            # see request-access.html), so someone typing their real
            # institutional/LDAP password here - a reasonable assumption
            # when the username IS their institution ID - will always fail,
            # and a plain "invalid username or password" gives no hint why.
            if user["guid"] and user["guid"] == username:

                institution_id_label = os.getenv("INSTITUTION_ID_LABEL", "Institution ID")

                raise HTTPException(
                    status_code=401,
                    detail=(
                        f"Invalid password. Note: currently logging in with your "
                        f"{institution_id_label} does not check your institutional/LDAP "
                        "password - Please, use the password you set when you "
                        "activated your catalogue account, or use 'Forgot "
                        "your password?' if you don't remember it."
                    )
                )

            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET last_login_at = NOW() WHERE user_id = %s",
                (user["user_id"],),
            )
        conn.commit()

    finally:

        conn.close()

    session_payload = {
        "username": user["username"],
        "email": user["email"],
        "display_name": user["full_name"],
        "role": user["role"],
        "exp": int(time.time()) + SESSION_DURATION_SECONDS,
    }

    token = sign_payload(session_payload)

    secure_cookie = os.getenv("APP_COOKIE_SECURE", "false").lower() == "true"

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=SESSION_DURATION_SECONDS,
        path="/",
    )

    return {
        "status": "ok",
        "user": {
            "username": user["username"],
            "email": user["email"],
            "display_name": user["full_name"],
            "role": user["role"],
        },
    }


@app.post("/api/logout")
def logout(response: Response):
    """Clear the session cookie."""
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"status": "ok"}


@app.get("/api/me")
def me(user: dict = Depends(require_user)):
    """Return the currently-authenticated user's identity/role."""
    return {
        "authenticated": True,
        "user": {
            "username": user["username"],
            "email": user["email"],
            "display_name": user["display_name"],
            "role": user["role"],
        },
    }



def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "catalogue_mariadb"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

class _SafeFormatDict(dict):
    """Leaves unknown {placeholder} tokens in a template untouched
    instead of raising, so a template referencing a field we don't
    have context for still sends a (partially) useful email."""

    def __missing__(self, key):
        return "{" + key + "}"


def notify_registration_event(cur, event: str, context: dict) -> None:
    """Send the admin-configured registration notification email, if enabled.

    event is "submission" or "activation":
      - "submission" is gated by registration_notify_on_submission and uses
        the registration_notification_subject/message templates.
      - "activation" is gated by registration_notify_on_activation and uses
        the registration_activation_subject/message templates.
    Both send to registration_notification_email. Templates may reference
    `context` keys as {placeholders}, e.g. "{full_name}".

    Failures are logged, not raised, so a broken mail server never breaks
    the request submission or account activation.
    """

    setting_prefix = (
        "registration_notification" if event == "submission" else "registration_activation"
    )
    subject_key = f"{setting_prefix}_subject"
    message_key = f"{setting_prefix}_message"

    cur.execute(
        """
        SELECT setting_name, setting_value
        FROM system_settings
        WHERE setting_name IN (
            'registration_notification_email',
            %s,
            %s,
            'registration_notify_on_submission',
            'registration_notify_on_activation'
        )
        """,
        (subject_key, message_key),
    )

    settings = {row["setting_name"]: row["setting_value"] for row in cur.fetchall()}

    if settings.get(f"registration_notify_on_{event}") != "true":
        return

    to_address = settings.get("registration_notification_email")
    if not to_address:
        return

    subject_template = settings.get(subject_key) or "Catalogue notification"
    message_template = settings.get(message_key) or ""

    safe_context = _SafeFormatDict(context)
    subject = subject_template.format_map(safe_context)
    body = message_template.format_map(safe_context)

    try:
        send_email(to_address, subject, body, from_override=os.getenv("MAIL_FROM_REGISTRATION"))
    except Exception as exc:
        print(f"Failed to send registration {event} notification email:", exc)


def send_activation_invite(cur, context: dict) -> None:
    """Email a newly-approved user their activation link.

    Unlike notify_registration_event, this always sends - it isn't an
    optional admin FYI, it's the only way the user can ever activate
    the account. Best-effort: a broken mail server must not break the
    approval itself.
    """

    cur.execute(
        """
        SELECT setting_name, setting_value
        FROM system_settings
        WHERE setting_name IN (
            'activation_invite_subject',
            'activation_invite_message'
        )
        """
    )

    settings = {row["setting_name"]: row["setting_value"] for row in cur.fetchall()}

    subject_template = settings.get("activation_invite_subject") or "Activate your Catalogue account"
    message_template = settings.get("activation_invite_message") or (
        "Your Virtual Microscopy Catalogue account has been approved.\n\n"
        "Activate your account here:\n{activation_link}\n\n"
        "This link expires on {expires_at}."
    )

    safe_context = _SafeFormatDict(context)
    subject = subject_template.format_map(safe_context)
    body = message_template.format_map(safe_context)

    try:
        send_email(context["email"], subject, body, from_override=os.getenv("MAIL_FROM_REGISTRATION"))
    except Exception as exc:
        print("Failed to send activation invite email:", exc)


def send_password_reset_email(cur, context: dict) -> None:
    """Email a user the link to reset their password.

    Always sends - it's the only way to complete the reset, not an
    optional admin FYI. Best-effort: a broken mail server must not
    break the request endpoint.
    """

    cur.execute(
        """
        SELECT setting_name, setting_value
        FROM system_settings
        WHERE setting_name IN (
            'password_reset_subject',
            'password_reset_message'
        )
        """
    )

    settings = {row["setting_name"]: row["setting_value"] for row in cur.fetchall()}

    subject_template = settings.get("password_reset_subject") or "Reset your Catalogue password"
    message_template = settings.get("password_reset_message") or (
        "We received a request to reset the password for your Virtual "
        "Microscopy Catalogue account ({username}).\n\n"
        "Reset your password here:\n{reset_link}\n\n"
        "This link expires on {expires_at}.\n\n"
        "If you did not request this, you can safely ignore this email."
    )

    safe_context = _SafeFormatDict(context)
    subject = subject_template.format_map(safe_context)
    body = message_template.format_map(safe_context)

    try:
        send_email(context["email"], subject, body, from_override=os.getenv("MAIL_FROM_REGISTRATION"))
    except Exception as exc:
        print("Failed to send password reset email:", exc)


def send_activation_confirmation_email(cur, context: dict) -> None:
    """Email the user themselves confirming their account is now active.

    Separate from notify_registration_event(cur, "activation", ...),
    which is the optional admin-facing FYI - this one goes to the user
    who just activated, always. Best-effort: a broken mail server must
    not break the activation itself.
    """

    cur.execute(
        """
        SELECT setting_name, setting_value
        FROM system_settings
        WHERE setting_name IN (
            'activation_confirmation_subject',
            'activation_confirmation_message'
        )
        """
    )

    settings = {row["setting_name"]: row["setting_value"] for row in cur.fetchall()}

    subject_template = settings.get("activation_confirmation_subject") or "Your Catalogue account is now active"
    message_template = settings.get("activation_confirmation_message") or (
        "Hi {full_name},\n\n"
        "Your Virtual Microscopy Catalogue account ({username}) has been "
        "activated successfully. You can now log in here:\n{login_link}\n\n"
        "If you did not perform this activation, please contact us immediately."
    )

    safe_context = _SafeFormatDict(context)
    subject = subject_template.format_map(safe_context)
    body = message_template.format_map(safe_context)

    try:
        send_email(context["email"], subject, body, from_override=os.getenv("MAIL_FROM_REGISTRATION"))
    except Exception as exc:
        print("Failed to send activation confirmation email:", exc)


def _validate_password_policy(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not any(char.isupper() for char in password):
        raise HTTPException(status_code=400, detail="Password must include an uppercase letter")
    if not any(char.islower() for char in password):
        raise HTTPException(status_code=400, detail="Password must include a lowercase letter")
    if not any(char.isdigit() for char in password):
        raise HTTPException(status_code=400, detail="Password must include a number")


def _log_password_reset_event(
    cur,
    event_type: str,
    email_provided: str,
    user_id: Optional[int],
    http_request: Optional[Request],
) -> None:
    remote_addr = None
    user_agent = None

    if http_request is not None:
        remote_addr = http_request.client.host if http_request.client else None
        user_agent = http_request.headers.get("user-agent", "")

    cur.execute(
        """
        INSERT INTO password_reset_log (
            user_id,
            email_provided,
            event_type,
            remote_addr,
            user_agent
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            user_id,
            email_provided,
            event_type,
            remote_addr,
            user_agent[:500] if user_agent else None,
        ),
    )


def clean_value(value: Any):
    if value == "NULL":
        return None
    if isinstance(value, str) and value.strip().upper() == "NULL":
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value

def clean_row(row: Optional[dict]):
    if row is None:
        return None
    return {key: clean_value(value) for key, value in row.items()}


def clean_rows(rows):
    return [clean_row(row) for row in rows]


def build_share_path(path_prefix: str, relative_path: Optional[str], separator: str):
    if not relative_path:
        return None

    cleaned = relative_path.strip().strip("/\\")
    parts = cleaned.replace("\\", "/").split("/")
    prefix = path_prefix.rstrip("/\\")

    return prefix + separator + separator.join(parts)


def get_share_root(os_key: str):
    os_key = (os_key or "linux").lower()

    if os_key == "windows":
        return {
            "os": "windows",
            "display_name": "Windows",
            "path_prefix": os.getenv("SHARE_ROOT_WINDOWS", r"\\share\virtual-microscopy"),
            "separator": "\\",
        }

    if os_key == "macos":
        return {
            "os": "macos",
            "display_name": "macOS",
            "path_prefix": os.getenv("SHARE_ROOT_MACOS", "/Volumes/virtual-microscopy"),
            "separator": "/",
        }

    return {
        "os": "linux",
        "display_name": "Linux",
        "path_prefix": os.getenv("SHARE_ROOT_LINUX", "/mnt/virtual-microscopy"),
        "separator": "/",
    }


@app.get("/api/health")
def health():
    """Unauthenticated liveness check - does not touch the database."""
    return {
        "status": "ok",
        "service": "catalogue-backend"
    }


@app.get("/api/public-config")
def public_config():
    """Unauthenticated, deployment-wide display config - safe to fetch
    before login. Currently just the label a deploying institution wants
    used for their external identity number (e.g. "University ID", "UID",
    "Student/Staff Number") in place of this repo's generic default -
    the underlying field itself is always called guid in the database and
    API regardless of what it's labelled here."""
    return {
        "institution_id_label": os.getenv("INSTITUTION_ID_LABEL", "Institution ID"),
    }


@app.get("/api/db-health")
def db_health(user: dict = Depends(require_user)):
    """Logged-in database connectivity check - returns the connected
    database name and current slide count, or a generic error. Requires
    login (unlike /api/health, which is the real unauthenticated liveness
    probe) since the database name and raw exception text (which can
    include the DB username and internal network details, e.g. a real
    "Access denied for user '...'@'10.x.x.x'" message) shouldn't be
    exposed to an anonymous caller."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE() AS database_name")
            row = cur.fetchone()

            cur.execute("SELECT COUNT(*) AS slide_count FROM slides")
            slide_count = cur.fetchone()["slide_count"]

        conn.close()

        return {
            "status": "ok",
            "database": row["database_name"],
            "slide_count": slide_count,
        }

    except Exception as exc:
        print("db_health check failed:", exc)
        return {
            "status": "error",
        }


@app.get("/api/thumbnail-paths/{slide_id}")
def thumbnail_paths(slide_id: int):
    """Build the search/detail/large thumbnail URLs for a slide_id.
    Purely derived from the ID - does not check the slide exists or that
    the thumbnail files are actually present on disk."""
    return {
        "slide_id": slide_id,
        "thumbnails": {
            "search": f"/thumbnails/512/{slide_id}.jpg",
            "detail": f"/thumbnails/1024/{slide_id}.jpg",
            "large": f"/thumbnails/2048/{slide_id}.jpg",
        }
    }

class AccessRequestCreate(BaseModel):
    full_name: str
    email: str
    institution: str
    guid: Optional[str] = None
    authentication_method: str = "LOCAL"
    request_reason: str

class ContactMessageCreate(BaseModel):
    name: str = Field(max_length=255)
    email: str = Field(max_length=255)
    message: str = Field(max_length=10000)

class ActivationRequest(BaseModel):
    token: str
    password: str

class PasswordResetRequestCreate(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class ProfileUpdateRequest(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    institution: Optional[str] = None
    guid: Optional[str] = None
    authentication_method: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


@app.get("/api/me/profile")
def get_profile(user: dict = Depends(require_user)):
    """Return the current user's own profile fields (not the password hash)."""
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    user_id,
                    username,
                    email,
                    full_name,
                    institution,
                    guid,
                    role,
                    authentication_method,
                    account_status
                FROM users
                WHERE username = %s
                """,
                (user["username"],),
            )
            row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="User profile not found")

        return {
            "status": "ok",
            "profile": clean_row(row),
        }

    finally:
        conn.close()


@app.put("/api/me/profile")
def update_profile(
    response: Response,
    payload: ProfileUpdateRequest,
    user: dict = Depends(require_user),
):
    """Update the current user's own profile fields, and/or change their
    password (requires current_password when setting new_password). If a
    GUID is present, username must match it. Re-signs the session cookie
    since the username/role embedded in it may have changed."""
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    user_id,
                    username,
                    email,
                    full_name,
                    institution,
                    guid,
                    role,
                    authentication_method,
                    account_status,
                    password_hash
                FROM users
                WHERE username = %s
                """,
                (user["username"],),
            )
            current_row = cur.fetchone()

        if not current_row:
            raise HTTPException(status_code=404, detail="User profile not found")

        updates = []
        params = []

        def normalize_optional(value: Optional[str]) -> Optional[str]:
            if value is None:
                return None
            cleaned = str(value).strip()
            return cleaned or None

        if payload.username is not None:
            new_username = normalize_optional(payload.username)
            if not new_username:
                raise HTTPException(status_code=400, detail="Username cannot be empty")
            if payload.guid is not None:
                guid_value = normalize_optional(payload.guid)
                if guid_value and new_username != guid_value:
                    raise HTTPException(status_code=400, detail="When a GUID is present, the username must match the GUID")
            elif current_row["guid"]:
                if new_username != current_row["guid"]:
                    raise HTTPException(status_code=400, detail="When a GUID is present, the username must match the GUID")
            if new_username != current_row["username"]:
                with conn.cursor() as cur:
                    # Checked against all three columns, not just username -
                    # username/email/guid share one authentication namespace
                    # (login accepts any of the three), so a new username
                    # colliding with another user's email or guid is exactly
                    # as ambiguous at login time as colliding with their
                    # username would be.
                    cur.execute(
                        "SELECT user_id FROM users WHERE (username = %s OR email = %s OR guid = %s) AND user_id != %s",
                        (new_username, new_username, new_username, current_row["user_id"]),
                    )
                    duplicate = cur.fetchone()
                if duplicate:
                    raise HTTPException(status_code=400, detail="Username is already in use")
                updates.append("username = %s")
                params.append(new_username)

        if payload.email is not None:
            new_email = normalize_optional(payload.email)
            if not new_email:
                raise HTTPException(status_code=400, detail="Email cannot be empty")
            if new_email != current_row["email"]:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT user_id FROM users WHERE (username = %s OR email = %s OR guid = %s) AND user_id != %s",
                        (new_email, new_email, new_email, current_row["user_id"]),
                    )
                    duplicate = cur.fetchone()
                if duplicate:
                    raise HTTPException(status_code=400, detail="Email is already in use")
                updates.append("email = %s")
                params.append(new_email)

        if payload.full_name is not None:
            full_name = normalize_optional(payload.full_name)
            if full_name is not None and full_name != current_row["full_name"]:
                updates.append("full_name = %s")
                params.append(full_name)

        if payload.institution is not None:
            institution = normalize_optional(payload.institution)
            if institution != current_row["institution"]:
                updates.append("institution = %s")
                params.append(institution)

        if payload.guid is not None:
            guid = normalize_optional(payload.guid)
            if guid != current_row["guid"]:
                if guid:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT user_id FROM users WHERE (username = %s OR email = %s OR guid = %s) AND user_id != %s",
                            (guid, guid, guid, current_row["user_id"]),
                        )
                        duplicate = cur.fetchone()
                    if duplicate:
                        raise HTTPException(status_code=400, detail="GUID is already in use")
                updates.append("guid = %s")
                params.append(guid)

        if payload.authentication_method is not None:
            auth_method = normalize_optional(payload.authentication_method)
            if auth_method not in (None, "LOCAL", "LDAP"):
                raise HTTPException(status_code=400, detail="Invalid authentication method")
            if auth_method is not None and auth_method != current_row["authentication_method"]:
                updates.append("authentication_method = %s")
                params.append(auth_method)

        if payload.new_password is not None:
            if not payload.current_password:
                raise HTTPException(status_code=400, detail="Current password is required")
            _validate_password_policy(payload.new_password)
            try:
                password_hasher.verify(current_row["password_hash"], payload.current_password)
            except Exception as exc:
                raise HTTPException(status_code=400, detail="Current password is invalid") from exc

            updates.append("password_hash = %s")
            params.append(password_hasher.hash(payload.new_password))

        if not updates:
            return {
                "status": "ok",
                "profile": clean_row(current_row),
            }

        with conn.cursor() as cur:
            query = "UPDATE users SET " + ", ".join(updates) + " WHERE user_id = %s"
            params.append(current_row["user_id"])
            cur.execute(query, tuple(params))
            conn.commit()

            cur.execute(
                """
                SELECT
                    user_id,
                    username,
                    email,
                    full_name,
                    institution,
                    guid,
                    role,
                    authentication_method,
                    account_status
                FROM users
                WHERE user_id = %s
                """,
                (current_row["user_id"],),
            )
            updated_row = cur.fetchone()

        session_payload = {
            "username": updated_row["username"],
            "email": updated_row["email"],
            "display_name": updated_row["full_name"],
            "role": updated_row["role"],
            "exp": int(time.time()) + SESSION_DURATION_SECONDS,
        }

        token = sign_payload(session_payload)
        secure_cookie = os.getenv("APP_COOKIE_SECURE", "false").lower() == "true"

        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            httponly=True,
            secure=secure_cookie,
            samesite="lax",
            max_age=SESSION_DURATION_SECONDS,
            path="/",
        )

        return {
            "status": "ok",
            "profile": clean_row(updated_row),
        }

    finally:
        conn.close()


def _record_blocked_access_request(cur, email, full_name, reason, remote_addr, user_agent):
    cur.execute(
        """
        INSERT INTO access_request_blocked_attempts (
            attempted_email,
            attempted_full_name,
            reason,
            remote_addr,
            user_agent
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            email,
            full_name,
            reason,
            remote_addr,
            user_agent[:500] if user_agent else None,
        ),
    )


def _notify_system_admins_of_blocked_request(cur, email, full_name, reason_text):
    cur.execute(
        """
        SELECT email
        FROM users
        WHERE role = 'system_admin'
          AND account_status = 'ACTIVE'
          AND email IS NOT NULL
          AND email != ''
        """
    )

    subject = "Catalogue - Blocked duplicate access request"
    body = (
        "A blocked access request attempt was recorded.\n\n"
        f"Name: {full_name}\n"
        f"Email: {email}\n"
        f"Reason: {reason_text}\n\n"
        "This has been logged in access_request_blocked_attempts for review."
    )

    for row in cur.fetchall():
        try:
            send_email(row["email"], subject, body, from_override=os.getenv("MAIL_FROM_REGISTRATION"))
        except Exception as exc:
            print("Failed to send blocked-request alert to", row["email"], ":", exc)


@app.post("/api/access-request")
def create_access_request(request: AccessRequestCreate, http_request: Request):
    """Public, unauthenticated self-service request for a new account.
    If the email already has an account or a pending request, returns a
    409 explaining which, and separately logs the attempt to
    access_request_blocked_attempts and emails system_admins about it."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            remote_addr = http_request.client.host if http_request.client else None
            user_agent = http_request.headers.get("user-agent", "")

            cur.execute(
                "SELECT user_id FROM users WHERE email = %s",
                (request.email,),
            )
            existing_user = cur.fetchone()

            cur.execute(
                """
                SELECT request_id FROM access_requests
                WHERE email = %s AND status = 'PENDING'
                """,
                (request.email,),
            )
            existing_pending = cur.fetchone()

            if existing_user or existing_pending:
                reason = "email_already_registered" if existing_user else "duplicate_pending_request"
                reason_text = (
                    "An account with this email already exists."
                    if existing_user
                    else "A request for this email is already pending review."
                )

                _record_blocked_access_request(
                    cur, request.email, request.full_name, reason, remote_addr, user_agent
                )
                _notify_system_admins_of_blocked_request(
                    cur, request.email, request.full_name, reason_text
                )

                conn.commit()

                raise HTTPException(status_code=409, detail=reason_text)

            cur.execute(
                """
                INSERT INTO access_requests (
                    full_name,
                    email,
                    institution,
                    guid,
                    authentication_method,
                    request_reason
                )
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (
                    request.full_name,
                    request.email,
                    request.institution,
                    request.guid,
                    request.authentication_method,
                    request.request_reason
                )
            )

            conn.commit()

            print(
                "REGISTRATION REQUEST:",
                request.full_name,
                request.email,
                request.institution
            )

            notify_registration_event(
                cur,
                "submission",
                {
                    "full_name": request.full_name,
                    "email": request.email,
                    "institution": request.institution,
                    "guid": request.guid,
                    "authentication_method": request.authentication_method,
                    "request_reason": request.request_reason,
                    "requested_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                },
            )

            return {
                "status": "success",
                "message": "Access request submitted"
            }

    finally:
        conn.close()

@app.get("/api/access-requests")
def list_access_requests(
    user: dict = Depends(require_admin),
):
    """List every access request (all statuses), newest first."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    request_id,
                    full_name,
                    email,
                    institution,
                    guid,
                    authentication_method,
                    request_reason,
                    status,
                    submitted_at,
                    reviewed_at,
                    reviewed_by,
                    review_notes
                FROM access_requests
                ORDER BY submitted_at DESC
                """
            )

            return cur.fetchall()

    finally:
        conn.close()


@app.post("/api/access-requests/{request_id}/approve")
def approve_access_request(
    request_id: int,
    user: dict = Depends(require_admin),
):
    """Approve a pending access request. Creates a new PENDING_ACTIVATION
    user, a 7-day activation token, and emails the activation link. The
    username is the request's GUID when one was supplied (matching the
    "username must equal the GUID" rule /api/me/profile already enforces
    on updates - falling back to a collision-safe first-initial.surname.
    user_id when there's no GUID, or the GUID is somehow already taken).
    If a user with this email already exists (e.g. a duplicate request),
    just marks the request APPROVED without creating a second account."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    full_name,
                    email,
                    institution,
                    guid,
                    authentication_method
                FROM access_requests
                WHERE request_id = %s
                """,
                (request_id,)
            )

            request_row = cur.fetchone()

            if not request_row:

                return {
                    "status": "error",
                    "message": "Request not found"
                }

            cur.execute(
                """
                SELECT user_id
                FROM users
                WHERE email = %s
                """,
                (request_row["email"],)
            )

            existing_user = cur.fetchone()

            if existing_user:

                cur.execute(
                    """
                    UPDATE access_requests
                    SET
                        status = 'APPROVED',
                        reviewed_at = NOW(),
                        reviewed_by = %s
                    WHERE request_id = %s
                    """,
                    (
                        user["username"],
                        request_id
                    )
                )

                conn.commit()

                return {
                    "status": "success",
                    "message": "User account already exists"
                }


            cur.execute(
                """
                INSERT INTO users (
                    username,
                    email,
                    full_name,
                    institution,
                    guid,
                    authentication_method,
                    account_status,
                    approved_by,
                    approved_at
                )
                VALUES (
                    '',%s,%s,%s,%s,%s,
                    'PENDING_ACTIVATION',
                    %s,
                    NOW()
                )
                """,
                (
                    request_row["email"],
                    request_row["full_name"],
                    request_row["institution"],
                    request_row["guid"],
                    request_row["authentication_method"],
                    user["username"]
                )
            )

            user_id = cur.lastrowid
            activation_token = str(
                uuid.uuid4()
            )

            expires_at = (
                datetime.utcnow()
                + timedelta(days=7)
            )

            cur.execute(
                """
                INSERT INTO user_activation_tokens (
                    user_id,
                    activation_token,
                    expires_at
                )
                VALUES (
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    user_id,
                    activation_token,
                    expires_at
                )
            )

            username = None

            if request_row["guid"]:
                cur.execute(
                    """
                    SELECT user_id
                    FROM users
                    WHERE username = %s AND user_id != %s
                    """,
                    (request_row["guid"], user_id)
                )
                if not cur.fetchone():
                    username = request_row["guid"]

            if username is None:
                name_parts = (
                    request_row["full_name"]
                    .strip()
                    .lower()
                    .split()
                )

                first_initial = name_parts[0][0]

                surname = name_parts[-1]

                username = (
                    f"{first_initial}."
                    f"{surname}."
                    f"{user_id}"
                )

            cur.execute(
                """
                UPDATE users
                SET username = %s
                WHERE user_id = %s
                """,
                (
                    username,
                    user_id
                )
            )

            cur.execute(
                """
                UPDATE access_requests
                SET
                    status = 'APPROVED',
                    reviewed_at = NOW(),
                    reviewed_by = %s
                WHERE request_id = %s
                """,
                (
                    user["username"],
                    request_id
                )
            )

            conn.commit()

            activation_link = (
                os.getenv("APP_BASE_URL", "http://localhost:8080")
                + "/activate.html?token="
                + activation_token
            )

            send_activation_invite(
                cur,
                {
                    "full_name": request_row["full_name"],
                    "username": username,
                    "email": request_row["email"],
                    "activation_link": activation_link,
                    "expires_at": expires_at.strftime("%Y-%m-%d %H:%M UTC"),
                },
            )

            return {
                "status": "success",
                "message": f"Request {request_id} approved"
            }

    finally:
        conn.close()

@app.post("/api/access-requests/{request_id}/reject")
def reject_access_request(
    request_id: int,
    user: dict = Depends(require_admin),
):
    """Mark a pending access request REJECTED. No account or notification
    email is created."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE access_requests
                SET
                    status = 'REJECTED',
                    reviewed_at = NOW(),
                    reviewed_by = %s
                WHERE request_id = %s
                """,
                (
                    user["username"],
                    request_id,
                )
            )

            conn.commit()

            return {
                "status": "success",
                "message": f"Request {request_id} rejected"
            }

    finally:
        conn.close()

@app.get("/api/activation-token/{token}")
def get_activation_token(token: str):
    """Public lookup used by the activation page to show which account a
    token belongs to before the user sets a password. Does not check
    expiry/used_at itself - just returns them for the caller to check."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    u.user_id,
                    u.username,
                    u.email,
                    u.guid,
                    u.account_status,
                    t.expires_at,
                    t.used_at
                FROM user_activation_tokens t
                JOIN users u
                    ON u.user_id = t.user_id
                WHERE t.activation_token = %s
                """,
                (token,)
            )

            row = cur.fetchone()

            if not row:

                raise HTTPException(
                    status_code=404,
                    detail="Activation token not found"
                )

            return {
                "user_id": row["user_id"],
                "username": row["username"],
                "email": row["email"],
                "guid": row["guid"],
                "account_status": row["account_status"],
                "expires_at": row["expires_at"],
                "used_at": row["used_at"]
            }

    finally:
        conn.close()

@app.post("/api/activate-account")
def activate_account(
    request: ActivationRequest
):
    """Set the initial password for a PENDING_ACTIVATION account and mark
    it ACTIVE, consuming the one-time activation token (400 if already
    used or expired). Sends an activation-confirmation email."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    t.user_id,
                    t.used_at,
                    t.expires_at,
                    u.username,
                    u.email,
                    u.full_name
                FROM user_activation_tokens t
                JOIN users u
                    ON u.user_id = t.user_id
                WHERE t.activation_token = %s
                """,
                (request.token,)
            )

            token_row = cur.fetchone()

            if not token_row:

                raise HTTPException(
                    status_code=404,
                    detail="Activation token not found"
                )

            if token_row["used_at"]:

                raise HTTPException(
                    status_code=400,
                    detail="Activation token already used"
                )

            if (
                token_row["expires_at"]
                and token_row["expires_at"] < datetime.utcnow()
            ):

                raise HTTPException(
                    status_code=400,
                    detail="Activation token expired"
                )

            _validate_password_policy(request.password)

            password_hash = (
                password_hasher.hash(
                    request.password
                )
            )

            cur.execute(
                """
                UPDATE users
                SET
                    password_hash = %s,
                    account_status = 'ACTIVE'
                WHERE user_id = %s
                """,
                (
                    password_hash,
                    token_row["user_id"]
                )
            )

            cur.execute(
                """
                UPDATE user_activation_tokens
                SET used_at = NOW()
                WHERE activation_token = %s
                """,
                (request.token,)
            )

            conn.commit()

            notify_registration_event(
                cur,
                "activation",
                {
                    "full_name": token_row["full_name"],
                    "username": token_row["username"],
                    "email": token_row["email"],
                    "activated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                },
            )

            send_activation_confirmation_email(
                cur,
                {
                    "full_name": token_row["full_name"],
                    "username": token_row["username"],
                    "email": token_row["email"],
                    "activated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                    "login_link": os.getenv("APP_BASE_URL", "http://localhost:8080") + "/login.html",
                },
            )

            return {
                "status": "success",
                "message": "Account activated"
            }

    finally:
        conn.close()

@app.post("/api/request-password-reset")
def request_password_reset(
    request: PasswordResetRequestCreate,
    http_request: Request,
):
    """Public, unauthenticated "forgot password" request - issues a
    2-hour reset token and emails the link if the account exists and is
    ACTIVE. Every outcome (unknown email, inactive account, success) is
    logged to password_reset_log for abuse monitoring."""

    email = request.email.strip()

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT user_id, username, email, full_name, account_status
                FROM users
                WHERE email = %s
                """,
                (email,),
            )

            user_row = cur.fetchone()

            # Always returns the same generic 200 regardless of whether the
            # email matched a real, active account - a distinct 404/400 here
            # would let anyone enumerate which email addresses have accounts
            # (and which of those are inactive) just by trying them against
            # this endpoint, no login attempt needed.
            generic_response = {
                "status": "success",
                "message": "If an account exists for that email address, a password reset link has been sent.",
            }

            if not user_row:
                _log_password_reset_event(cur, "invalid_email", email, None, http_request)
                conn.commit()
                return generic_response

            if user_row["account_status"] != "ACTIVE":
                _log_password_reset_event(cur, "inactive_account", email, user_row["user_id"], http_request)
                conn.commit()
                return generic_response

            reset_token = str(uuid.uuid4())
            expires_at = datetime.utcnow() + timedelta(hours=2)

            cur.execute(
                """
                INSERT INTO password_reset_tokens (
                    user_id,
                    reset_token,
                    expires_at
                )
                VALUES (%s, %s, %s)
                """,
                (user_row["user_id"], reset_token, expires_at),
            )

            _log_password_reset_event(cur, "requested", email, user_row["user_id"], http_request)

            conn.commit()

            reset_link = (
                os.getenv("APP_BASE_URL", "http://localhost:8080")
                + "/reset-password.html?token="
                + reset_token
            )

            send_password_reset_email(
                cur,
                {
                    "full_name": user_row["full_name"],
                    "username": user_row["username"],
                    "email": user_row["email"],
                    "reset_link": reset_link,
                    "expires_at": expires_at.strftime("%Y-%m-%d %H:%M UTC"),
                },
            )

            return generic_response

    finally:
        conn.close()

@app.get("/api/password-reset-token/{token}")
def get_password_reset_token(token: str):
    """Public lookup used by the reset-password page to show which
    account a token belongs to. Does not check expiry/used_at itself -
    just returns them for the caller to check."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    u.user_id,
                    u.username,
                    u.email,
                    t.expires_at,
                    t.used_at
                FROM password_reset_tokens t
                JOIN users u
                    ON u.user_id = t.user_id
                WHERE t.reset_token = %s
                """,
                (token,),
            )

            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Password reset link not found")

            return {
                "user_id": row["user_id"],
                "username": row["username"],
                "email": row["email"],
                "expires_at": row["expires_at"],
                "used_at": row["used_at"],
            }

    finally:
        conn.close()

@app.post("/api/reset-password")
def reset_password(
    request: PasswordResetConfirm,
    http_request: Request,
):
    """Set a new password from a reset token (400 if already used or
    expired), enforcing the password policy. Consumes the token."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    t.user_id,
                    t.used_at,
                    t.expires_at,
                    u.username,
                    u.email,
                    u.full_name
                FROM password_reset_tokens t
                JOIN users u
                    ON u.user_id = t.user_id
                WHERE t.reset_token = %s
                """,
                (request.token,),
            )

            token_row = cur.fetchone()

            if not token_row:
                raise HTTPException(status_code=404, detail="Password reset link not found")

            if token_row["used_at"]:
                raise HTTPException(status_code=400, detail="This password reset link has already been used")

            if (
                token_row["expires_at"]
                and token_row["expires_at"] < datetime.utcnow()
            ):
                raise HTTPException(status_code=400, detail="This password reset link has expired")

            _validate_password_policy(request.new_password)

            password_hash = password_hasher.hash(request.new_password)

            cur.execute(
                """
                UPDATE users
                SET password_hash = %s
                WHERE user_id = %s
                """,
                (password_hash, token_row["user_id"]),
            )

            cur.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = NOW()
                WHERE reset_token = %s
                """,
                (request.token,),
            )

            _log_password_reset_event(
                cur, "completed", token_row["email"], token_row["user_id"], http_request
            )

            conn.commit()

            return {
                "status": "success",
                "message": "Password reset"
            }

    finally:
        conn.close()

@app.get("/api/contribution-ticker")
def contribution_ticker():
    """Public, unauthenticated: homepage scrolling ticker of contributor
    thank-you messages. Admin-controlled via contribution_ticker_enabled /
    contribution_ticker_message in system_settings - ships disabled with
    no default message. Before enabling: this formats every active
    contributor's full_name and username into the public response, and
    username is the same field used for an institutional GUID/ID number
    where one is configured - enabling this publishes real names and
    institutional IDs to anyone, logged in or not."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT setting_name, setting_value
                FROM system_settings
                WHERE setting_name IN (
                    'contribution_ticker_enabled',
                    'contribution_ticker_message'
                )
                """
            )

            settings = {row["setting_name"]: row["setting_value"] for row in cur.fetchall()}

            template = settings.get("contribution_ticker_message") or ""

            if settings.get("contribution_ticker_enabled") != "true" or not template:
                return {"enabled": False, "messages": []}

            cur.execute(
                """
                SELECT full_name, username, contributions_accepted_count
                FROM users
                WHERE account_status = 'ACTIVE'
                  AND contributions_accepted_count > 0
                ORDER BY contributions_accepted_count DESC, full_name
                """
            )

            messages = [
                template.format_map(
                    _SafeFormatDict(
                        {
                            "full_name": row["full_name"],
                            "username": row["username"],
                            "contributions_accepted_count": row["contributions_accepted_count"],
                        }
                    )
                )
                for row in cur.fetchall()
            ]

            return {"enabled": bool(messages), "messages": messages}

    finally:
        conn.close()


@app.get("/api/featured-slides")
def featured_slides():
    """Public (unauthenticated) - random active slide candidates for the
    homepage. Returns 10 candidates rather than the 4 actually displayed -
    this endpoint has no way to know which slides have a generated
    thumbnail (that's nginx-served static content, not something the
    backend has filesystem access to check), so the frontend preloads each
    candidate image client-side and renders only the first 4 that actually
    load, silently skipping any that 404.
    """

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    slide_id,
                    filename
                FROM slides
                WHERE asset_status = 'ACTIVE'
                ORDER BY RAND()
                LIMIT 10
                """
            )

            return cur.fetchall()

    finally:
        conn.close()



@app.get("/api/search")
def search_slides(
    user: dict = Depends(require_user),
    q: Optional[str] = None,
    slide_id: Optional[int] = None,
    filename: Optional[str] = None,
    organ: Optional[str] = None,
    species: Optional[str] = None,
    stain: Optional[str] = None,
    tissue: Optional[str] = None,
    has_slide_annotations: Optional[bool] = None,
    has_legacy_notes: Optional[bool] = None,
    is_z_stack: Optional[bool] = None,
    is_multiview: Optional[bool] = None,
    is_comparison_slide: Optional[bool] = None,
    legacy_thick_section: Optional[bool] = None,
    active_only: bool = True,
    order_by: str = Query("slide_id"),
    order_dir: str = Query("asc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Main slide search/filter/listing endpoint - free-text q (matches
    metadata, legacy notes, filenames), exact/range filters, the various
    has_*/is_* quick-filter booleans, sorting, and pagination."""
    where = []
    params = []

    if active_only:
        where.append("s.asset_status = 'ACTIVE'")


    if slide_id is not None:
        where.append("s.slide_id = %s")
        params.append(slide_id)


    if filename:
        # Digit-boundary match, not a plain substring - searching "780"
        # should find "Slide780" or "DR 402,780" but not match as part
        # of a longer digit run like "1780". A plain \b word boundary
        # is too strict here (it would also reject "Slide780", since
        # a letter directly touching a digit has no \b between them) -
        # only reject when the match is directly flanked by *another
        # digit*, not by a letter or punctuation.
        where.append("s.filename REGEXP %s")
        params.append(r"(?<![0-9])" + re.escape(filename.strip()) + r"(?![0-9])")


    if q:
        like = f"%{q}%"

        where.append("""
            (
                s.filename LIKE %s OR
                s.archive_relative_path LIKE %s OR
                sm.organ LIKE %s OR
                sm.species LIKE %s OR
                sm.stain LIKE %s OR
                sd.canonical_stain LIKE %s OR
                sd.stain_family LIKE %s OR
                sm.description LIKE %s OR
                sm.notes LIKE %s OR

                EXISTS (
                    SELECT 1
                    FROM v_slide_legacy_notes vdn
                    WHERE vdn.slide_id = s.slide_id
                      AND (
                           vdn.annotation_title LIKE %s
                         OR vdn.note_text LIKE %s
                      )
                )
            )
        """)
        params.extend([like] * 11)

    if organ:
        where.append("sm.organ LIKE %s")
        params.append(f"%{organ}%")

    if species:
        where.append("sm.species LIKE %s")
        params.append(f"%{species}%")

    if stain:
        like = f"%{stain}%"
        where.append("(sm.stain LIKE %s OR sd.canonical_stain LIKE %s OR sd.stain_family LIKE %s)")
        params.extend([like, like, like])

    if tissue:
        where.append("""
            EXISTS (
                SELECT 1
                FROM slide_tissue_annotations sta
                JOIN tissue_dictionary td
                    ON td.tissue_id = sta.tissue_id
                WHERE sta.slide_id = s.slide_id
                  AND (
                    td.tissue_name LIKE %s OR
                    td.canonical_tissue LIKE %s OR
                    td.tissue_category LIKE %s OR
                    td.tissue_group LIKE %s
                  )
            )
        """)
        like = f"%{tissue}%"
        params.extend([like, like, like, like])

    if has_slide_annotations is True:
        where.append("EXISTS (SELECT 1 FROM slide_annotations sa2 WHERE sa2.slide_id = s.slide_id AND sa2.flagged_incorrect = 0)")
    elif has_slide_annotations is False:
        where.append("NOT EXISTS (SELECT 1 FROM slide_annotations sa2 WHERE sa2.slide_id = s.slide_id AND sa2.flagged_incorrect = 0)")

    if has_legacy_notes is True:
        where.append("EXISTS (SELECT 1 FROM slide_legacy_curation_links sda WHERE sda.slide_id = s.slide_id)")
    elif has_legacy_notes is False:
        where.append("NOT EXISTS (SELECT 1 FROM slide_legacy_curation_links sda WHERE sda.slide_id = s.slide_id)")

    if is_z_stack is True:
        where.append("(sm.is_z_stack = 1 OR sm.z_plane_count > 1)")
    elif is_z_stack is False:
        where.append("(sm.is_z_stack IS NULL OR sm.is_z_stack = 0) AND (sm.z_plane_count IS NULL OR sm.z_plane_count <= 1)")

    if is_multiview is True:
        where.append("sm.meaningful_view_count > 1")
    elif is_multiview is False:
        where.append("(sm.meaningful_view_count IS NULL OR sm.meaningful_view_count <= 1)")

    if is_comparison_slide is True:
        where.append("sm.is_comparison_slide = 1")
    elif is_comparison_slide is False:
        where.append("(sm.is_comparison_slide IS NULL OR sm.is_comparison_slide = 0)")

    if legacy_thick_section is True:
        where.append("sm.legacy_thick_section = 1")
    elif legacy_thick_section is False:
        where.append("(sm.legacy_thick_section IS NULL OR sm.legacy_thick_section = 0)")

    where_sql = ""
    if where:
        where_sql = "WHERE " + " AND ".join(where)

    order_map = {
        "slide_id": "s.slide_id",
        "organ": "COALESCE(sm.organ, '')",
        "species": "COALESCE(sm.species, '')",
        "stain": "COALESCE(sd.canonical_stain, sm.stain, '')",
        "magnification": "COALESCE(s.objective_magnifications, '')",
        "format": "COALESCE(s.slide_format, '')",
        "random": "RAND()",
    }

    order_key = (order_by or "slide_id").lower()
    order_expr = order_map.get(order_key, "s.slide_id")

    if order_key == "random":
        order_sql = "RAND()"
    else:
        direction = "DESC" if (order_dir or "").lower() == "desc" else "ASC"
        order_sql = f"{order_expr} {direction}, s.slide_id ASC"

    sql = f"""
        SELECT
            s.slide_id,
            s.filename,
            s.archive_relative_path,
            s.slide_format,
            s.asset_status,
            s.metadata_status,
            s.file_size_bytes,
            s.width_pixels,
            s.height_pixels,
            s.objective_magnifications,

            sm.organ,
            sm.species,
            sm.stain AS raw_stain,
            COALESCE(sd.canonical_stain, sm.stain) AS canonical_stain,
            sd.stain_family,
            sm.description,
            sm.meaningful_view_count,
            sm.is_comparison_slide,
            sm.is_z_stack,
            sm.z_plane_count,
            sm.legacy_thick_section,

            (
                SELECT GROUP_CONCAT(
                    DISTINCT COALESCE(td.canonical_tissue, td.tissue_name)
                    ORDER BY COALESCE(td.canonical_tissue, td.tissue_name)
                    SEPARATOR '; '
                )
                FROM slide_tissue_annotations sta2
                JOIN tissue_dictionary td
                    ON td.tissue_id = sta2.tissue_id
                WHERE sta2.slide_id = s.slide_id
            ) AS tissue_summary,

            CASE
                WHEN sm.meaningful_view_count IS NOT NULL
                     AND sm.meaningful_view_count > 1
                THEN 1 ELSE 0
            END AS is_multiview,

            EXISTS (
                SELECT 1
                FROM slide_annotations sa
                WHERE sa.slide_id = s.slide_id AND sa.flagged_incorrect = 0
            ) AS has_slide_annotations,

            EXISTS (
                SELECT 1
                FROM slide_tissue_annotations sta
                WHERE sta.slide_id = s.slide_id
            ) AS has_tissue_annotations,

            EXISTS (
                SELECT 1
                FROM slide_legacy_curation_links sda
                WHERE sda.slide_id = s.slide_id
            ) AS has_legacy_notes

        FROM slides s
        LEFT JOIN slide_metadata sm
            ON sm.slide_id = s.slide_id
        LEFT JOIN stain_dictionary sd
            ON sd.original_stain = sm.stain
        {where_sql}
        ORDER BY {order_sql}
        LIMIT %s OFFSET %s
    """

    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM slides s
        LEFT JOIN slide_metadata sm
            ON sm.slide_id = s.slide_id
        LEFT JOIN stain_dictionary sd
            ON sd.original_stain = sm.stain
        {where_sql}
    """

    params_for_count = list(params)
    params_for_results = list(params) + [limit, offset]

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(count_sql, params_for_count)
            total = cur.fetchone()["total"]

            cur.execute(sql, params_for_results)
            rows = cur.fetchall()
    finally:
        conn.close()

    results = []
    for row in clean_rows(rows):
        slide_id = row["slide_id"]
        row["thumbnails"] = {
            "search": f"/thumbnails/512/{slide_id}.jpg",
            "detail": f"/thumbnails/1024/{slide_id}.jpg",
            "large": f"/thumbnails/2048/{slide_id}.jpg",
        }
        results.append(row)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": results,
    }




@app.get("/api/dictionaries/{dictionary_name}")
def dictionary_values(
    dictionary_name: str,
    user: dict = Depends(require_user),
):
    """Dictionary values for the metadata-correction form's dropdowns.

    Unlike /api/admin/dictionaries, this is available to any logged-in
    user (not just admins), and also covers tissue.
    """

    dictionary_name = dictionary_name.lower()

    if dictionary_name not in {"organ", "tissue", "species", "stain"}:
        raise HTTPException(status_code=400, detail="Unsupported dictionary")

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            if dictionary_name == "organ":
                cur.execute(
                    """
                    SELECT DISTINCT
                        organ_name AS value,
                        COALESCE(canonical_organ, organ_name) AS label
                    FROM organ_dictionary
                    WHERE active = 1
                    ORDER BY label, value
                    """
                )

            elif dictionary_name == "tissue":
                cur.execute(
                    """
                    SELECT DISTINCT
                        tissue_name AS value,
                        COALESCE(canonical_tissue, tissue_name) AS label
                    FROM tissue_dictionary
                    WHERE active = 1
                    ORDER BY label, value
                    """
                )

            elif dictionary_name == "species":
                cur.execute(
                    """
                    SELECT DISTINCT
                        species_name AS value,
                        COALESCE(canonical_species, species_name) AS label
                    FROM species_dictionary
                    WHERE active = 1
                    ORDER BY label, value
                    """
                )

            else:
                cur.execute(
                    """
                    SELECT DISTINCT
                        original_stain AS value,
                        COALESCE(canonical_stain, original_stain) AS label
                    FROM stain_dictionary
                    WHERE original_stain IS NOT NULL
                    ORDER BY label, value
                    """
                )

            rows = clean_rows(cur.fetchall())

    finally:
        conn.close()

    return {
        "dictionary": dictionary_name,
        "values": rows,
    }


@app.post("/api/slides/{slide_id}/metadata-correction")
def create_metadata_correction(
    slide_id: int,
    request: Request,
    payload: dict = Body(...),
    user: dict = Depends(require_user),
):
    """Submit a metadata correction (organ/tissue/species/stain/description/
    notes/general_comment) for review - creates a slide_corrections row
    with feedback_source='metadata' and increments the submitter's
    contributions_count."""
    feedback_type = str(payload.get("feedback_type", "general_comment")).strip()
    current_value = payload.get("current_value")
    suggested_value = payload.get("suggested_value")
    feedback_text = str(payload.get("feedback_text", "")).strip()

    allowed_types = {"organ", "tissue", "species", "stain", "description", "notes", "general_comment"}

    if feedback_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid feedback type")

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT filename
                FROM slides
                WHERE slide_id = %s
                """,
                (slide_id,),
            )
            slide = cur.fetchone()

            if slide is None:
                raise HTTPException(status_code=404, detail="Slide not found")

            remote_addr = None
            if request.client:
                remote_addr = request.client.host

            user_agent = request.headers.get("user-agent", "")

            cur.execute(
                """
                INSERT INTO slide_corrections (
                    slide_id,
                    slide_filename,
                    feedback_source,
                    feedback_type,
                    current_value,
                    suggested_value,
                    feedback_text,
                    submitter_username,
                    submitter_email,
                    submitter_display_name,
                    submitter_role,
                    remote_addr,
                    user_agent
                )
                VALUES (
                    %s, %s, 'metadata',
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s
                )
                """,
                (
                    slide_id,
                    slide["filename"],
                    feedback_type,
                    current_value,
                    suggested_value,
                    feedback_text,
                    user.get("username"),
                    user.get("email"),
                    user.get("display_name"),
                    user.get("role"),
                    remote_addr,
                    user_agent[:500] if user_agent else None,
                ),
            )

            feedback_id = cur.lastrowid

            cur.execute(
                """
                UPDATE users
                SET contributions_count = contributions_count + 1
                WHERE username = %s
                """,
                (user.get("username"),),
            )

        conn.commit()

        return {
            "status": "ok",
            "feedback_id": feedback_id,
            "feedback_source": "metadata",
            "message": "Metadata feedback submitted for review",
        }

    except HTTPException:
        raise

    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        conn.close()


@app.post("/api/slides/{slide_id}/annotation-feedback")
def create_annotation_feedback(
    slide_id: int,
    request: Request,
    payload: dict = Body(...),
    user: dict = Depends(require_user),
):
    """Report an existing slide annotation as correct/incorrect, for
    review - creates a slide_corrections row with
    feedback_source='slide_annotation'. If accepted with verdict
    'incorrect', the annotation gets hidden (slide_annotations.
    flagged_incorrect) once a reviewer approves it."""
    annotation_id = payload.get("annotation_id")
    verdict = str(payload.get("verdict", "")).strip().lower()
    feedback_text = str(payload.get("feedback_text", "")).strip()

    if verdict not in ("correct", "incorrect"):
        raise HTTPException(status_code=400, detail="verdict must be 'correct' or 'incorrect'")

    if not annotation_id:
        raise HTTPException(status_code=400, detail="annotation_id is required")

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM slides WHERE slide_id = %s", (slide_id,))
            slide = cur.fetchone()

            if slide is None:
                raise HTTPException(status_code=404, detail="Slide not found")

            cur.execute(
                "SELECT annotation_id FROM slide_annotations WHERE annotation_id = %s AND slide_id = %s",
                (annotation_id, slide_id),
            )
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Annotation not found on this slide")

            remote_addr = None
            if request.client:
                remote_addr = request.client.host

            user_agent = request.headers.get("user-agent", "")

            cur.execute(
                """
                INSERT INTO slide_corrections (
                    slide_id,
                    slide_filename,
                    feedback_source,
                    feedback_type,
                    source_annotation_id,
                    suggested_value,
                    feedback_text,
                    submitter_username,
                    submitter_email,
                    submitter_display_name,
                    submitter_role,
                    remote_addr,
                    user_agent
                )
                VALUES (
                    %s, %s, 'slide_annotation', 'annotation_review',
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s
                )
                """,
                (
                    slide_id,
                    slide["filename"],
                    annotation_id,
                    verdict,
                    feedback_text,
                    user.get("username"),
                    user.get("email"),
                    user.get("display_name"),
                    user.get("role"),
                    remote_addr,
                    user_agent[:500] if user_agent else None,
                ),
            )

            feedback_id = cur.lastrowid

            cur.execute(
                """
                UPDATE users
                SET contributions_count = contributions_count + 1
                WHERE username = %s
                """,
                (user.get("username"),),
            )

        conn.commit()

        return {
            "status": "ok",
            "feedback_id": feedback_id,
            "feedback_source": "slide_annotation",
            "message": "Annotation feedback submitted for review",
        }

    except HTTPException:
        raise

    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        conn.close()


@app.get("/api/slides/{slide_id}")
def get_slide(slide_id: int, os_key: str = Query("linux", alias="os"), user: dict = Depends(require_user)):
    """Full slide detail: metadata, technical metadata, thumbnails,
    annotations (excluding flagged_incorrect ones), legacy contributor
    notes, expert notes, and an OS-specific share path for the given
    os_key (linux/windows/macos)."""
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.slide_id,
                    s.inventory_id,
                    s.filename,
                    s.physical_path,
                    s.archive_relative_path,
                    s.slide_format,
                    s.file_size_bytes,
                    s.width_pixels,
                    s.height_pixels,
                    s.metadata_status,
                    s.asset_status,
                    s.created_date,
                    s.objective_magnifications,

                    sm.organ,
                    sm.species,
                    sm.stain AS raw_stain,
                    COALESCE(sd.canonical_stain, sm.stain) AS canonical_stain,
                    sd.stain_family,
                    sd.normalisation_status AS stain_normalisation_status,
                    sm.magnification,
                    sm.description,
                    sm.notes,
                    sm.is_comparison_slide,
                    sm.meaningful_view_count,
                    sm.image_dimensions,
                    sm.is_z_stack,
                    sm.z_plane_count,
                    sm.legacy_thick_section,

                    stm.openslide_status,
                    stm.openslide_vendor,
                    stm.openslide_scan_date,
                    stm.openslide_quickhash,
                    stm.openslide_associated_image_count,
                    stm.tiffslide_status,
                    stm.tiffslide_vendor,
                    stm.openslide_mpp_x,
                    stm.openslide_mpp_y,
                    stm.tiffslide_mpp_x,
                    stm.tiffslide_mpp_y,
                    stm.collection_name,
                    stm.image_count,
                    stm.image_names,
                    stm.is_multiview,
                    stm.view_count,
                    stm.z_spacing,
                    stm.technical_metadata_source,
                    stm.technical_metadata_updated

                FROM slides s
                LEFT JOIN slide_metadata sm
                    ON sm.slide_id = s.slide_id
                LEFT JOIN stain_dictionary sd
                    ON sd.original_stain = sm.stain
                LEFT JOIN slide_technical_metadata stm
                    ON stm.slide_id = s.slide_id
                WHERE s.slide_id = %s
                """,
                (slide_id,),
            )
            core = cur.fetchone()

            if core is None:
                raise HTTPException(status_code=404, detail="Slide not found")

            cur.execute(
                """
                SELECT
                    sta.tissue_id,
                    td.tissue_name,
                    td.canonical_tissue,
                    td.tissue_category,
                    td.tissue_group,
                    sta.evidence_source,
                    sta.review_status,
                    sta.confidence,
                    sta.notes,
                    sta.created_date
                FROM slide_tissue_annotations sta
                JOIN tissue_dictionary td
                    ON td.tissue_id = sta.tissue_id
                WHERE sta.slide_id = %s
                ORDER BY td.tissue_name
                """,
                (slide_id,),
            )
            tissues = cur.fetchall()

            cur.execute(
                """
                SELECT
                    annotation_id,
                    annotation_type,
                    rect_x,
                    rect_y,
                    rect_w,
                    rect_h,
                    window_x,
                    window_y,
                    window_w,
                    window_h,
                    arrow_start_x,
                    arrow_start_y,
                    arrow_end_x,
                    arrow_end_y,
                    zoom,
                    focal_plane,
                    current_frame,
                    title,
                    description,
                    annotation_date,
                    line_colour,
                    drawing,
                    moveable,
                    area,
                    filled,
                    invisible,
                    tma_core,
                    owner,
                    source_annotation_id,
                    created_date,
                    updated_date
                FROM slide_annotations
                WHERE slide_id = %s AND flagged_incorrect = 0
                ORDER BY annotation_id
                """,
                (slide_id,),
            )
            annotations = cur.fetchall()

            cur.execute(
                """
                SELECT
                    legacy_curation_id,
                    annotation_title,
                    note_text,
                    confidence_score,
                    reconciliation_method,
                    reconciliation_notes
                FROM v_slide_legacy_notes
                WHERE slide_id = %s
                ORDER BY legacy_curation_id
                """,
                (slide_id,),
            )
            legacy_notes = cur.fetchall()

            cur.execute(
                """
                SELECT
                    note_id,
                    slide_id,
                    author_username,
                    author_display_name,
                    note_title,
                    note_text,
                    created_at,
                    updated_at
                FROM slide_expert_notes
                WHERE slide_id = %s
                ORDER BY created_at DESC
                """,
                (slide_id,),
            )
            expert_notes = cur.fetchall()

    finally:
        conn.close()

    core = clean_row(core)
    tissues = clean_rows(tissues)
    annotations = clean_rows(annotations)
    legacy_notes = clean_rows(legacy_notes)
    expert_notes = clean_rows(expert_notes)

    share_root = get_share_root(os_key)
    resolved_path = build_share_path(
        share_root["path_prefix"],
        core["archive_relative_path"],
        share_root["separator"],
    )

    return {
        "slide_id": slide_id,
        "identity": {
            "slide_id": core["slide_id"],
            "inventory_id": core["inventory_id"],
            "filename": core["filename"],
            "slide_format": core["slide_format"],
            "asset_status": core["asset_status"],
            "metadata_status": core["metadata_status"],
            "created_date": core["created_date"],
        },
        "file_location": {
            "archive_relative_path": core["archive_relative_path"],
            "selected_os": share_root["os"],
            "display_name": share_root["display_name"],
            "resolved_share_path": resolved_path,
            "physical_path_admin_only": core["physical_path"],
        },
        "metadata": {
            "organ": core["organ"],
            "species": core["species"],
            "raw_stain": core["raw_stain"],
            "canonical_stain": core["canonical_stain"],
            "stain_family": core["stain_family"],
            "stain_normalisation_status": core["stain_normalisation_status"],
            "magnification": core["magnification"],
            "description": core["description"],
            "notes": core["notes"],
            "is_comparison_slide": core["is_comparison_slide"],
            "meaningful_view_count": core["meaningful_view_count"],
            "image_dimensions": core["image_dimensions"],
            "is_z_stack": core["is_z_stack"],
            "z_plane_count": core["z_plane_count"],
            "legacy_thick_section": core["legacy_thick_section"],
        },
        "technical": {
            "file_size_bytes": core["file_size_bytes"],
            "width_pixels": core["width_pixels"],
            "height_pixels": core["height_pixels"],
            "objective_magnifications": core["objective_magnifications"],
            "openslide_status": core["openslide_status"],
            "openslide_vendor": core["openslide_vendor"],
            "openslide_scan_date": core["openslide_scan_date"],
            "openslide_quickhash": core["openslide_quickhash"],
            "openslide_associated_image_count": core["openslide_associated_image_count"],
            "tiffslide_status": core["tiffslide_status"],
            "tiffslide_vendor": core["tiffslide_vendor"],
            "openslide_mpp_x": core["openslide_mpp_x"],
            "openslide_mpp_y": core["openslide_mpp_y"],
            "tiffslide_mpp_x": core["tiffslide_mpp_x"],
            "tiffslide_mpp_y": core["tiffslide_mpp_y"],
            "collection_name": core["collection_name"],
            "image_count": core["image_count"],
            "image_names": core["image_names"],
            "is_multiview": core["is_multiview"],
            "view_count": core["view_count"],
            "z_spacing": core["z_spacing"],
            "technical_metadata_source": core["technical_metadata_source"],
            "technical_metadata_updated": core["technical_metadata_updated"],
        },
        "thumbnails": {
            "search": f"/thumbnails/512/{slide_id}.jpg",
            "detail": f"/thumbnails/1024/{slide_id}.jpg",
            "large": f"/thumbnails/2048/{slide_id}.jpg",
        },
        "tissue_annotations": tissues,
        "slide_annotations": annotations,
        "legacy_notes": legacy_notes,
        "expert_notes": expert_notes,
    }


@app.get("/api/expert-notes")
def list_expert_notes(
    slide_id: Optional[int] = None,
    user: dict = Depends(require_user),
):
    """List expert-authored notes, newest first, optionally filtered to
    one slide_id."""
    where_sql = ""
    params = []
    if slide_id:
        where_sql = "WHERE en.slide_id = %s"
        params.append(slide_id)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    en.note_id,
                    en.slide_id,
                    s.filename AS slide_filename,
                    en.author_username,
                    en.author_display_name,
                    en.note_title,
                    en.note_text,
                    en.created_at,
                    en.updated_at
                FROM slide_expert_notes en
                JOIN slides s ON s.slide_id = en.slide_id
                {where_sql}
                ORDER BY en.created_at DESC
                """,
                params,
            )
            notes = clean_rows(cur.fetchall())
    finally:
        conn.close()

    return {"status": "ok", "notes": notes}


@app.post("/api/slides/{slide_id}/expert-notes")
def create_expert_note(
    slide_id: int,
    payload: dict = Body(...),
    user: dict = Depends(require_permission("expert_notes.write")),
):
    """Create a new expert-authored note on a slide."""
    note_title = payload.get("note_title")
    note_text = str(payload.get("note_text", "")).strip()

    if not note_text:
        raise HTTPException(status_code=400, detail="note_text is required")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT slide_id FROM slides WHERE slide_id = %s", (slide_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Slide not found")

            cur.execute(
                """
                INSERT INTO slide_expert_notes (
                    slide_id, author_username, author_display_name, note_title, note_text
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    slide_id,
                    user.get("username"),
                    user.get("display_name"),
                    note_title,
                    note_text,
                ),
            )
            note_id = cur.lastrowid

        conn.commit()
        return {"status": "ok", "note_id": note_id}

    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.patch("/api/expert-notes/{note_id}")
def update_expert_note(
    note_id: int,
    payload: dict = Body(...),
    user: dict = Depends(require_permission("expert_notes.write")),
):
    """Overwrite an expert note's title/text. Unlike legacy_curation
    edits, no prior-version history is kept here - this is a direct
    overwrite of the expert's own note content."""
    note_title = payload.get("note_title")
    note_text = str(payload.get("note_text", "")).strip()

    if not note_text:
        raise HTTPException(status_code=400, detail="note_text is required")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT note_id FROM slide_expert_notes WHERE note_id = %s", (note_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Expert note not found")

            cur.execute(
                """
                UPDATE slide_expert_notes
                SET note_title = %s, note_text = %s
                WHERE note_id = %s
                """,
                (note_title, note_text, note_id),
            )

        conn.commit()
        return {"status": "ok", "note_id": note_id}

    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.delete("/api/expert-notes/{note_id}")
def delete_expert_note(
    note_id: int,
    user: dict = Depends(require_permission("expert_notes.write")),
):
    """Permanently delete an expert note. No soft-delete or history."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT note_id FROM slide_expert_notes WHERE note_id = %s", (note_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Expert note not found")

            cur.execute("DELETE FROM slide_expert_notes WHERE note_id = %s", (note_id,))

        conn.commit()
        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.patch("/api/legacy-notes/{curation_id}")
def update_legacy_note(
    curation_id: int,
    payload: dict = Body(...),
    user: dict = Depends(require_permission("expert_notes.write")),
):
    """Lets an expert edit the legacy contributor note content directly
    (trusted, no approval step) - the prior title/text is always captured
    in legacy_curation_edit_history first, so nothing is silently lost if
    an edit turns out to be wrong.
    """
    note_text = str(payload.get("note_text", "")).strip()
    annotation_title = payload.get("annotation_title")

    if not note_text:
        raise HTTPException(status_code=400, detail="note_text is required")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT annotation_title, note_text FROM legacy_curation WHERE curation_id = %s",
                (curation_id,),
            )
            current = cur.fetchone()

            if current is None:
                raise HTTPException(status_code=404, detail="Legacy contributor record not found")

            cur.execute(
                """
                INSERT INTO legacy_curation_edit_history (
                    curation_id, previous_annotation_title, previous_note_text, edited_by_username
                )
                VALUES (%s, %s, %s, %s)
                """,
                (curation_id, current["annotation_title"], current["note_text"], user.get("username")),
            )

            cur.execute(
                """
                UPDATE legacy_curation
                SET annotation_title = %s, note_text = %s
                WHERE curation_id = %s
                """,
                (annotation_title, note_text, curation_id),
            )

        conn.commit()
        return {"status": "ok", "curation_id": curation_id}

    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


_ANNOTATION_COLUMNS = """
    annotation_id,
    annotation_type,
    rect_x,
    rect_y,
    rect_w,
    rect_h,
    arrow_start_x,
    arrow_start_y,
    arrow_end_x,
    arrow_end_y,
    zoom,
    title,
    description,
    drawing,
    invisible
"""


def _ome_xml_filename(slide_id, filename, arrow_style, has_arrow):
    name_hint = slugify_filename_hint(filename)
    parts = [f"slide_{slide_id}"]
    if name_hint:
        parts.append(name_hint)
    if has_arrow:
        parts.append(arrow_style_filename_label(arrow_style))
    parts.append("annotations")
    return "_".join(parts) + ".ome.xml"


@app.get("/api/slides/{slide_id}/annotations-ome-xml")
def get_slide_annotations_ome_xml(
    slide_id: int,
    apply_zoom: bool = Query(True, description="Multiply rect/point coordinates by each annotation's own 'zoom' field - still being verified against real data, see the comment at the top of annotation_ome_xml.py"),
    color: str = Query("00FF00", description="Annotation colour as a hex triplet (with or without a leading '#') - defaults to bright green, applied to every shape"),
    arrow_style: str = Query("<", description="Arrowhead placement for 'arrow'-type annotations: '<' (head at start), '>' (head at end), or '<>' (both ends). Original recording never stored which end originally had the arrowhead, so this is a chosen default, not recovered source data."),
    user: dict = Depends(require_user),
):
    """Generate a downloadable OME-XML file recreating this slide's stored
    annotations (rect/arrow/point etc.) as real ROIs, ready to import
    directly into OMERO via omero-roi-importer - no QuPath round-trip
    required. 404s if the slide has no non-flagged annotations."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT slide_id, filename, physical_path FROM slides WHERE slide_id = %s",
                (slide_id,),
            )
            slide = cur.fetchone()

            if slide is None:
                raise HTTPException(status_code=404, detail="Slide not found")

            cur.execute(
                f"""
                SELECT {_ANNOTATION_COLUMNS}
                FROM slide_annotations
                WHERE slide_id = %s AND flagged_incorrect = 0
                ORDER BY annotation_id
                """,
                (slide_id,),
            )
            annotations = cur.fetchall()
    finally:
        conn.close()

    slide = clean_row(slide)
    annotations = clean_rows(annotations)

    if not annotations:
        raise HTTPException(status_code=404, detail="This slide has no stored annotations")

    xml, _marked_invisible, _skipped = build_ome_xml(
        slide, annotations, physical_path=slide.get("physical_path"),
        apply_zoom=apply_zoom, color=parse_annotation_color(color),
        arrow_style=parse_annotation_arrow_style(arrow_style),
    )

    has_arrow = any((a.get("annotation_type") or "").lower() == "arrow" for a in annotations)
    filename = _ome_xml_filename(slide_id, slide.get("filename"), arrow_style, has_arrow)

    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/admin/slides/annotations-ome-xml-bulk")
def get_all_slides_annotations_ome_xml_bulk(
    apply_zoom: bool = Query(True),
    user: dict = Depends(require_system_admin),
):
    """Sysadmin-only bulk export: one OME-XML file per slide that has at
    least one non-flagged annotation, bundled into a single zip. Uses fixed
    defaults (bright green, arrowhead at the start) since there's no
    reasonable way to prompt per-slide in a bulk run."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT s.slide_id, s.filename, s.physical_path
                FROM slides s
                JOIN slide_annotations sa ON sa.slide_id = s.slide_id
                WHERE sa.flagged_incorrect = 0
                ORDER BY s.slide_id
                """
            )
            slides = cur.fetchall()

            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for slide_row in slides:
                    slide_id = slide_row["slide_id"]
                    with conn.cursor() as ann_cur:
                        ann_cur.execute(
                            f"""
                            SELECT {_ANNOTATION_COLUMNS}
                            FROM slide_annotations
                            WHERE slide_id = %s AND flagged_incorrect = 0
                            ORDER BY annotation_id
                            """,
                            (slide_id,),
                        )
                        annotations = ann_cur.fetchall()

                    slide = clean_row(slide_row)
                    annotations = clean_rows(annotations)
                    if not annotations:
                        continue

                    xml, _marked_invisible, _skipped = build_ome_xml(
                        slide, annotations, physical_path=slide.get("physical_path"),
                        apply_zoom=apply_zoom,
                        color=DEFAULT_ANNOTATION_COLOR, arrow_style=DEFAULT_ANNOTATION_ARROW_STYLE,
                    )
                    has_arrow = any((a.get("annotation_type") or "").lower() == "arrow" for a in annotations)
                    filename = _ome_xml_filename(
                        slide_id, slide.get("filename"), DEFAULT_ANNOTATION_ARROW_STYLE, has_arrow,
                    )
                    zf.writestr(filename, xml)
    finally:
        conn.close()

    buffer.seek(0)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="all_slide_annotations_ome_xml.zip"'},
    )


@app.get("/api/admin/dictionaries/{dictionary_name}")
def admin_dictionary_values(
    dictionary_name: str,
    admin_user: dict = Depends(require_admin),
):
    """Admin-only dictionary values, with extra organ_system/organ_group
    columns for organ - unlike the plain /api/dictionaries/{name} used by
    the correction form's dropdowns."""
    dictionary_name = dictionary_name.lower()

    if dictionary_name not in {"organ", "tissue", "species", "stain"}:
        raise HTTPException(status_code=400, detail="Unsupported dictionary")

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            if dictionary_name == "organ":
                cur.execute(
                    """
                    SELECT DISTINCT
                        organ_name AS value,
                        COALESCE(canonical_organ, organ_name) AS label,
                        organ_system,
                        organ_group
                    FROM organ_dictionary
                    WHERE active = 1
                    ORDER BY label, value
                    """
                )

            elif dictionary_name == "tissue":
                cur.execute(
                    """
                    SELECT DISTINCT
                        tissue_name AS value,
                        COALESCE(canonical_tissue, tissue_name) AS label,
                        tissue_category,
                        tissue_group
                    FROM tissue_dictionary
                    WHERE active = 1
                    ORDER BY label, value
                    """
                )

            elif dictionary_name == "species":
                cur.execute(
                    """
                    SELECT DISTINCT
                        species_name AS value,
                        COALESCE(canonical_species, species_name) AS label,
                        scientific_name,
                        species_group
                    FROM species_dictionary
                    WHERE active = 1
                    ORDER BY label, value
                    """
                )

            else:
                cur.execute(
                    """
                    SELECT DISTINCT
                        original_stain AS value,
                        COALESCE(canonical_stain, original_stain) AS label,
                        canonical_stain,
                        stain_family,
                        normalisation_status,
                        notes
                    FROM stain_dictionary
                    WHERE original_stain IS NOT NULL
                    ORDER BY label, value
                    """
                )

            rows = clean_rows(cur.fetchall())

    finally:
        conn.close()

    return {
        "dictionary": dictionary_name,
        "values": rows,
    }


@app.get("/api/admin/dictionaries-export")
def admin_export_dictionaries(admin_user: dict = Depends(require_admin)):
    """Full export of all five controlled-vocabulary tables, as JSON -
    for backup, sharing between deployments, or seeding a brand-new
    installation's dictionaries instead of starting empty (see
    seed_dictionaries.py, which loads exactly this shape). Uses natural
    keys (organ_name/tissue_name, not the auto-increment organ_id/
    tissue_id) for organ_tissue so the file is portable across databases
    - re-importing it doesn't depend on matching surrogate IDs.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM organ_dictionary ORDER BY organ_name")
            organ = clean_rows(cur.fetchall())

            cur.execute("SELECT * FROM tissue_dictionary ORDER BY tissue_name")
            tissue = clean_rows(cur.fetchall())

            cur.execute("SELECT * FROM species_dictionary ORDER BY species_name")
            species = clean_rows(cur.fetchall())

            cur.execute("SELECT * FROM stain_dictionary ORDER BY original_stain")
            stain = clean_rows(cur.fetchall())

            cur.execute(
                """
                SELECT o.organ_name, t.tissue_name, ot.relationship_type,
                       ot.notes, ot.review_status, ot.confidence
                FROM organ_tissue_dictionary ot
                JOIN organ_dictionary o ON o.organ_id = ot.organ_id
                JOIN tissue_dictionary t ON t.tissue_id = ot.tissue_id
                ORDER BY o.organ_name, t.tissue_name
                """
            )
            organ_tissue = clean_rows(cur.fetchall())
    finally:
        conn.close()

    return {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "organ": organ,
        "tissue": tissue,
        "species": species,
        "stain": stain,
        "organ_tissue": organ_tissue,
    }


@app.post("/api/admin/dictionaries/{dictionary_name}")
def admin_add_dictionary_value(
    dictionary_name: str,
    payload: dict = Body(...),
    admin_user: dict = Depends(require_admin),
):
    """Adds a brand-new term to a dictionary - used when a user's 'Other
    (not listed)' suggestion is a genuinely new organ/tissue/species/
    stain that isn't in the controlled vocabulary yet. Once added, it
    becomes selectable from apply-metadata-correction like any other
    dictionary value.
    """

    dictionary_name = dictionary_name.lower()
    value = str(payload.get("value", "")).strip()

    if dictionary_name not in {"organ", "tissue", "species", "stain"}:
        raise HTTPException(status_code=400, detail="Unsupported dictionary")

    if not value:
        raise HTTPException(status_code=400, detail="Value is required")

    table_and_column = {
        "organ": ("organ_dictionary", "organ_name"),
        "tissue": ("tissue_dictionary", "tissue_name"),
        "species": ("species_dictionary", "species_name"),
    }

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            if dictionary_name == "stain":
                # stain_dictionary has no active flag - original_stain is
                # the primary key itself.
                cur.execute(
                    """
                    INSERT IGNORE INTO stain_dictionary (original_stain)
                    VALUES (%s)
                    """,
                    (value,),
                )
            else:
                table, column = table_and_column[dictionary_name]
                cur.execute(
                    f"""
                    INSERT INTO {table} ({column}, active)
                    VALUES (%s, 1)
                    ON DUPLICATE KEY UPDATE active = 1
                    """,
                    (value,),
                )

        conn.commit()

    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        conn.close()

    return {
        "status": "ok",
        "dictionary": dictionary_name,
        "value": value,
    }


@app.post("/api/admin/dictionaries/stain/update")
def admin_update_stain_dictionary_entry(
    payload: dict = Body(...),
    admin_user: dict = Depends(require_system_admin),
):
    """Edits an existing stain_dictionary row's curated columns - unlike
    POST /api/admin/dictionaries/{name} (add a brand-new term), this
    requires original_stain to already exist. system_admin-only, stricter
    than the admin-level view/add-new endpoints: this is where a curator
    marks a stain value as stain_family='Comparison slide' (the existing
    convention driving is_comparison_slide - see sync_cmp_flags.py and
    the matching check in admin_apply_metadata_correction), which is a
    judgement call, not routine data entry."""

    original_stain = str(payload.get("original_stain", "")).strip()
    if not original_stain:
        raise HTTPException(status_code=400, detail="original_stain is required")

    canonical_stain = payload.get("canonical_stain")
    stain_family = payload.get("stain_family")
    normalisation_status = payload.get("normalisation_status")
    notes = payload.get("notes")

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM stain_dictionary WHERE original_stain = %s",
                (original_stain,),
            )
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Stain dictionary entry not found")

            cur.execute(
                """
                UPDATE stain_dictionary
                SET canonical_stain = %s,
                    stain_family = %s,
                    normalisation_status = %s,
                    notes = %s
                WHERE original_stain = %s
                """,
                (canonical_stain, stain_family, normalisation_status, notes, original_stain),
            )

            log_admin_action(
                conn, admin_user, "update_stain_dictionary", original_stain,
            )

        conn.commit()

    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        conn.close()

    return {"status": "ok", "original_stain": original_stain}


def _increment_accepted_contribution(cur, submitter_username):
    """DB half of rewarding a contribution - run inside the same
    transaction as the status change, before commit."""

    if submitter_username:
        cur.execute(
            """
            UPDATE users
            SET contributions_accepted_count = contributions_accepted_count + 1
            WHERE username = %s
            """,
            (submitter_username,),
        )


def _send_contribution_thanks(submitter_email, slide_id, body_intro):
    """Email half of rewarding a contribution - run after commit, so a
    slow/broken mail server never risks the DB change itself. Best-effort:
    failure is logged, not raised."""

    if not submitter_email:
        return

    slide_link = (
        os.getenv("APP_BASE_URL", "http://localhost:8080")
        + "/slide.html?id="
        + str(slide_id)
    )

    body = (
        f"{body_intro}\n\n"
        f"View the slide here:\n{slide_link}\n\n"
        "We appreciate you helping improve the Virtual Microscopy Catalogue."
    )

    try:
        send_email(submitter_email, f"Thank you for your suggestion - Slide {slide_id}", body)
    except Exception as exc:
        print("Failed to send contribution thank-you email:", exc)


def _update_correction_status(correction_id: int, payload: dict, acting_user: dict):
    """Shared review-decision logic for both the admin and reviewer
    review endpoints. Rejects self-review (submitter == acting_user) for
    everyone except system_admin, who has full authority and can approve
    their own submissions, logs the status change to
    slide_correction_actions, keeps slide_annotations.flagged_incorrect in
    sync with the current decision (reversibly), and emails the submitter
    a thank-you the first time a correction reaches 'resolved'."""
    status = str(payload.get("status", "")).strip()
    admin_notes = payload.get("admin_notes")

    allowed_status = {"new", "under_review", "accepted", "rejected", "resolved"}

    if status not in allowed_status:
        raise HTTPException(status_code=400, detail="Invalid correction status")

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT feedback_id, slide_id, status, submitter_username, submitter_email,
                       feedback_source, source_annotation_id, suggested_value
                FROM slide_corrections
                WHERE feedback_id = %s
                """,
                (correction_id,),
            )
            correction = cur.fetchone()

            if correction is None:
                raise HTTPException(status_code=404, detail="Correction not found")

            if (
                correction["submitter_username"] == acting_user.get("username")
                and acting_user.get("role") != "system_admin"
            ):
                raise HTTPException(
                    status_code=403,
                    detail="You can't review a correction you submitted yourself",
                )

            old_status = correction["status"]

            cur.execute(
                """
                UPDATE slide_corrections
                SET
                    status = %s,
                    admin_notes = %s,
                    reviewed_by_username = %s,
                    reviewed_at = NOW()
                WHERE feedback_id = %s
                """,
                (
                    status,
                    admin_notes,
                    acting_user.get("username"),
                    correction_id,
                ),
            )

            cur.execute(
                """
                INSERT INTO slide_correction_actions (
                    feedback_id,
                    slide_id,
                    action_type,
                    field_name,
                    old_value,
                    new_value,
                    action_notes,
                    performed_by_username
                )
                VALUES (%s, %s, 'status_update', 'status', %s, %s, %s, %s)
                """,
                (
                    correction_id,
                    correction["slide_id"],
                    old_status,
                    status,
                    admin_notes,
                    acting_user.get("username"),
                ),
            )

            if correction["feedback_source"] == "slide_annotation" and correction["source_annotation_id"]:
                # Ties the review decision directly to what's actually shown -
                # confirmed-incorrect annotations stop appearing on the slide
                # page, and re-opening/rejecting a decision brings them back
                # rather than requiring a separate one-way "apply" action.
                should_flag = status == "accepted" and correction["suggested_value"] == "incorrect"
                cur.execute(
                    "UPDATE slide_annotations SET flagged_incorrect = %s WHERE annotation_id = %s",
                    (1 if should_flag else 0, correction["source_annotation_id"]),
                )

            reward = (
                status == "resolved"
                and old_status != "resolved"
                and correction["submitter_username"] != acting_user.get("username")
            )

            if reward:
                _increment_accepted_contribution(cur, correction["submitter_username"])

        conn.commit()

        if reward:
            body_intro = f"Thank you for your suggestion on slide {correction['slide_id']}."
            body_intro += (
                f"\n\n{admin_notes}"
                if admin_notes
                else "\n\nWe've reviewed your correction and taken action based on it."
            )

            _send_contribution_thanks(correction["submitter_email"], correction["slide_id"], body_intro)

        return {
            "status": "ok",
            "feedback_id": correction_id,
            "new_status": status,
        }

    except HTTPException:
        raise

    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        conn.close()


@app.patch("/api/admin/corrections/{correction_id}/review")
def admin_update_correction_review(
    correction_id: int,
    payload: dict = Body(...),
    admin_user: dict = Depends(require_admin),
):
    """Admin review-decision endpoint - see _update_correction_status."""
    return _update_correction_status(correction_id, payload, admin_user)


@app.patch("/api/reviewer/corrections/{correction_id}/review")
def reviewer_update_correction_review(
    correction_id: int,
    payload: dict = Body(...),
    user: dict = Depends(require_permission("corrections.review")),
):
    """Reviewer-role review-decision endpoint (permission-gated via
    corrections.review) - see _update_correction_status."""
    return _update_correction_status(correction_id, payload, user)


@app.post("/api/admin/corrections/{correction_id}/apply")
def admin_apply_metadata_correction(
    correction_id: int,
    payload: dict = Body(...),
    admin_user: dict = Depends(require_admin),
):
    """Apply a metadata correction's suggested value to the actual
    slide_metadata row (or slide_tissue_annotations for field_name=
    'tissue') - dictionary-backed fields (organ/tissue/species/stain)
    are validated against the relevant dictionary first and rejected if
    not already present, not auto-created. Marks the correction
    'resolved' and thanks the submitter by email. Separate step from
    reviewing the correction - accepting it doesn't auto-apply."""
    field_name = str(payload.get("field_name", "")).strip().lower()
    new_value = str(payload.get("new_value", "")).strip()
    admin_notes = payload.get("admin_notes")

    dictionary_backed_fields = {"organ", "tissue", "species", "stain"}
    free_text_fields = {"description", "notes"}
    allowed_fields = dictionary_backed_fields | free_text_fields

    if field_name not in allowed_fields:
        raise HTTPException(
            status_code=400,
            detail="Only organ, tissue, species, stain, description, and notes can be corrected here",
        )

    if not new_value:
        raise HTTPException(status_code=400, detail="New value is required")

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    feedback_id,
                    slide_id,
                    feedback_source,
                    feedback_type,
                    status,
                    submitter_username,
                    submitter_email,
                    submitter_display_name
                FROM slide_corrections
                WHERE feedback_id = %s
                """,
                (correction_id,),
            )
            correction = cur.fetchone()

            if correction is None:
                raise HTTPException(status_code=404, detail="Correction not found")

            if correction["feedback_source"] != "metadata":
                raise HTTPException(status_code=400, detail="Only metadata corrections can be applied here")

            if correction["feedback_type"] != field_name:
                raise HTTPException(
                    status_code=400,
                    detail="Correction type does not match requested metadata field",
                )

            slide_id = correction["slide_id"]

            if field_name == "tissue":
                # Tissue isn't a slide_metadata column - it's a row in
                # slide_tissue_annotations keyed on (slide_id, tissue_id).
                # Every slide currently has at most one such row, so a
                # correction replaces it outright (delete then insert)
                # rather than updating a column in place.
                cur.execute(
                    """
                    SELECT tissue_id
                    FROM tissue_dictionary
                    WHERE active = 1
                      AND (
                        tissue_name = %s
                        OR canonical_tissue = %s
                      )
                    """,
                    (new_value, new_value),
                )
                tissue_row = cur.fetchone()

                if tissue_row is None:
                    raise HTTPException(
                        status_code=400,
                        detail="New value is not present in the tissue dictionary",
                    )

                new_tissue_id = tissue_row["tissue_id"]

                cur.execute(
                    """
                    SELECT td.tissue_name AS old_value
                    FROM slide_tissue_annotations sta
                    JOIN tissue_dictionary td ON td.tissue_id = sta.tissue_id
                    WHERE sta.slide_id = %s
                    """,
                    (slide_id,),
                )
                old_tissue_row = cur.fetchone()
                old_value = old_tissue_row["old_value"] if old_tissue_row else None

                cur.execute(
                    "DELETE FROM slide_tissue_annotations WHERE slide_id = %s",
                    (slide_id,),
                )
                cur.execute(
                    """
                    INSERT INTO slide_tissue_annotations (
                        slide_id, tissue_id, evidence_source, review_status, confidence, notes
                    )
                    VALUES (%s, %s, 'admin_correction', 'APPROVED', 'HIGH', %s)
                    """,
                    (slide_id, new_tissue_id, admin_notes),
                )

            elif field_name in dictionary_backed_fields:
                if field_name == "organ":
                    cur.execute(
                        """
                        SELECT COUNT(*) AS n
                        FROM organ_dictionary
                        WHERE active = 1
                          AND (
                            organ_name = %s
                            OR canonical_organ = %s
                          )
                        """,
                        (new_value, new_value),
                    )

                elif field_name == "species":
                    cur.execute(
                        """
                        SELECT COUNT(*) AS n
                        FROM species_dictionary
                        WHERE active = 1
                          AND (
                            species_name = %s
                            OR canonical_species = %s
                          )
                        """,
                        (new_value, new_value),
                    )

                else:
                    cur.execute(
                        """
                        SELECT COUNT(*) AS n
                        FROM stain_dictionary
                        WHERE original_stain = %s
                        """,
                        (new_value,),
                    )

                valid = cur.fetchone()["n"]

                if valid < 1:
                    raise HTTPException(
                        status_code=400,
                        detail="New value is not present in the relevant dictionary",
                    )

                column_name = field_name

                cur.execute(
                    f"""
                    SELECT {column_name} AS old_value
                    FROM slide_metadata
                    WHERE slide_id = %s
                    """,
                    (slide_id,),
                )
                row = cur.fetchone()

                if row is None:
                    raise HTTPException(status_code=404, detail="Slide metadata not found")

                old_value = row["old_value"]

                cur.execute(
                    f"""
                    UPDATE slide_metadata
                    SET {column_name} = %s
                    WHERE slide_id = %s
                    """,
                    (new_value, slide_id),
                )

                if field_name == "stain":
                    # Same check as sync_cmp_flags.py, applied immediately
                    # to this one slide rather than waiting for the next
                    # bulk run - additive only, never unmarks an existing
                    # CMP slide. See docs/database.md's stain_dictionary
                    # section for what this convention means.
                    cur.execute(
                        """
                        SELECT stain_family FROM stain_dictionary
                        WHERE original_stain = %s
                        """,
                        (new_value,),
                    )
                    stain_row = cur.fetchone()
                    if stain_row and stain_row["stain_family"] == "Comparison slide":
                        cur.execute(
                            """
                            UPDATE slide_metadata
                            SET is_comparison_slide = 1
                            WHERE slide_id = %s
                              AND (is_comparison_slide IS NULL OR is_comparison_slide = 0)
                            """,
                            (slide_id,),
                        )

            else:
                # description / notes - free text, nothing to validate
                # against a dictionary for.
                column_name = field_name

                cur.execute(
                    f"""
                    SELECT {column_name} AS old_value
                    FROM slide_metadata
                    WHERE slide_id = %s
                    """,
                    (slide_id,),
                )
                row = cur.fetchone()

                if row is None:
                    raise HTTPException(status_code=404, detail="Slide metadata not found")

                old_value = row["old_value"]

                cur.execute(
                    f"""
                    UPDATE slide_metadata
                    SET {column_name} = %s
                    WHERE slide_id = %s
                    """,
                    (new_value, slide_id),
                )

            cur.execute(
                """
                UPDATE slide_corrections
                SET
                    status = 'resolved',
                    admin_notes = %s,
                    reviewed_by_username = %s,
                    reviewed_at = NOW()
                WHERE feedback_id = %s
                """,
                (
                    admin_notes,
                    acting_user.get("username"),
                    correction_id,
                ),
            )

            reward = (
                correction["status"] != "resolved"
                and correction["submitter_username"] != admin_user.get("username")
            )

            if reward:
                _increment_accepted_contribution(cur, correction["submitter_username"])

            cur.execute(
                """
                INSERT INTO slide_correction_actions (
                    feedback_id,
                    slide_id,
                    action_type,
                    field_name,
                    old_value,
                    new_value,
                    action_notes,
                    performed_by_username
                )
                VALUES (%s, %s, 'metadata_update', %s, %s, %s, %s, %s)
                """,
                (
                    correction_id,
                    slide_id,
                    field_name,
                    old_value,
                    new_value,
                    admin_notes,
                    admin_user.get("username"),
                ),
            )

        conn.commit()

        if reward:
            body_intro = (
                f"Thank you for your suggestion on slide {slide_id}.\n\n"
                f"We've applied your correction:\n{field_name}: {old_value} -> {new_value}"
            )
            _send_contribution_thanks(correction["submitter_email"], slide_id, body_intro)

        return {
            "status": "ok",
            "feedback_id": correction_id,
            "slide_id": slide_id,
            "field_name": field_name,
            "old_value": old_value,
            "new_value": new_value,
            "message": "Metadata correction applied",
        }

    except HTTPException:
        raise

    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        conn.close()

@app.post("/api/admin/backup")
def admin_create_backup(
    admin_user: dict = Depends(require_system_admin),
):
    """Creates a new full database backup under catalogue/backups/database/full -
    the webpage-triggerable counterpart to backup_mariadb.sh (host CLI only).
    Only ever creates a new file: there is no list/read/delete endpoint here,
    and deliberately no restore endpoint at all - restore stays command-line
    only via restore_mariadb.sh."""

    try:
        backup_file = create_backup()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backup failed: {exc}")

    conn = get_db_connection()
    try:
        log_admin_action(conn, admin_user, "backup", backup_file.name)
        conn.commit()
    finally:
        conn.close()

    return {
        "filename": backup_file.name,
        "size_bytes": backup_file.stat().st_size,
    }


@app.post("/api/admin/sync-manual-thumbnails")
def admin_sync_manual_thumbnails(
    admin_user: dict = Depends(require_system_admin),
):
    """Converts every PNG waiting in /srv/manual_thumbnails (created by hand
    in QuPath for slides automated generation couldn't handle - see
    docs/thumbnail-maintenance.md) into the three real thumbnail sizes,
    backing up whatever was there before under /srv/thumbnail_backups. The
    docker-triggerable counterpart to running sync_manual_thumbnails.py
    directly; same underlying function either way."""

    try:
        results = sync_manual_thumbnails()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sync failed: {exc}")

    succeeded = [r for r in results if r["status"] != "ERROR"]
    failed = [r for r in results if r["status"] == "ERROR"]

    conn = get_db_connection()
    try:
        log_admin_action(
            conn, admin_user, "sync_manual_thumbnails",
            f"{len(succeeded)} succeeded, {len(failed)} failed",
        )
        conn.commit()
    finally:
        conn.close()

    return {"results": results, "succeeded": len(succeeded), "failed": len(failed)}


@app.post("/api/admin/sync-cmp-flags")
def admin_sync_cmp_flags(
    admin_user: dict = Depends(require_system_admin),
):
    """Sets slide_metadata.is_comparison_slide for every slide whose stain
    matches a stain_dictionary entry curated as stain_family='Comparison
    slide' (see docs/database.md's stain_dictionary section) - additive
    only, never unmarks an existing CMP slide. See sync_cmp_flags.py."""

    conn = get_db_connection()
    try:
        results = sync_cmp_flags(conn)
        conn.commit()

        log_admin_action(
            conn, admin_user, "sync_cmp_flags", f"{len(results)} slide(s) marked",
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Sync failed: {exc}")
    finally:
        conn.close()

    return {"results": results, "marked": len(results)}


@app.post("/api/admin/cleanup-backups")
def admin_cleanup_backups(
    payload: dict = Body(default={}),
    admin_user: dict = Depends(require_system_admin),
):
    """Deletes old full-database backups under catalogue/backups/database/full,
    keeping only the most recent `keep` (default 3). dry_run defaults True -
    the frontend calls this once to preview, then again with dry_run=False
    only after the admin confirms. The only place backups are ever listed
    or deleted from - restore and browsing/download stay CLI-only forever,
    unchanged. See cleanup_backups.py."""

    keep = payload.get("keep", 3)
    dry_run = payload.get("dry_run", True)

    try:
        keep = int(keep)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="keep must be a number")

    try:
        result = cleanup_backups(keep=keep, dry_run=dry_run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {exc}")

    if not dry_run and result["deleted"]:
        conn = get_db_connection()
        try:
            log_admin_action(
                conn, admin_user, "cleanup_backups",
                f"deleted {len(result['deleted'])}, kept {len(result['kept'])}",
            )
            conn.commit()
        finally:
            conn.close()

    return result


@app.post("/api/admin/sql")
def admin_run_sql(
    payload: dict = Body(...),
    admin_user: dict = Depends(require_system_admin),
):
    """Sysadmin-only raw SQL console. SELECT/UPDATE/DELETE/INSERT/ALTER/CREATE
    etc. are allowed - DROP and TRUNCATE are blocked by name, and only one
    statement may be submitted per call (see admin_sql.py). There is no
    restore endpoint anywhere in this API - undoing a mistake made here goes
    through a backup taken via POST /api/admin/backup and
    restore_mariadb.sh on the host, same as any other restore."""

    query = (payload or {}).get("query", "")

    try:
        validate_statement(query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)

            if cur.description is not None:
                rows = clean_rows(cur.fetchall())
                conn.commit()
                return {"rows": rows, "row_count": len(rows)}

            affected = cur.rowcount
            # SELECTs aren't logged (nothing changed) - anything else that
            # reaches this branch is a mutation, so it always is.
            log_admin_action(conn, admin_user, "sql", query)
            conn.commit()
            return {"affected_rows": affected}

    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        conn.close()


@app.get("/api/admin/audit-log")
def admin_list_audit_log(
    admin_user: dict = Depends(require_system_admin),
):
    """Every mutating action taken through POST /api/admin/backup or
    POST /api/admin/sql, newest first. Read-only actions (a SELECT, viewing
    this list itself) are never logged."""

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT audit_id, user_id, username, action, detail, created_at "
                "FROM admin_audit_log ORDER BY created_at DESC, audit_id DESC"
            )
            return clean_rows(cur.fetchall())
    finally:
        conn.close()


@app.delete("/api/admin/audit-log")
def admin_clear_audit_log(
    admin_user: dict = Depends(require_system_admin),
):
    """Clears the audit log, then writes a single marker row noting who
    cleared it and when - not a way around the clear (a genuine clear is
    the point), just a breadcrumb so an empty log isn't indistinguishable
    from one nothing was ever logged to."""

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM admin_audit_log")
        log_admin_action(conn, admin_user, "audit_log_cleared")
        conn.commit()
        return {"status": "cleared"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.get("/api/admin/users")
def admin_list_users(
    admin_user: dict = Depends(require_system_admin),
):
    """List every user account (all roles/statuses), alphabetical by
    full name."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    user_id,
                    username,
                    email,
                    full_name,
                    institution,
                    guid,
                    role,
                    authentication_method,
                    account_status,
                    contributions_count,
                    contributions_accepted_count,
                    approved_by,
                    approved_at,
                    created_at,
                    last_login_at
                FROM users
                ORDER BY full_name
                """
            )

            return clean_rows(cur.fetchall())

    finally:
        conn.close()


@app.get("/api/admin/blocked-access-requests")
def admin_list_blocked_access_requests(
    admin_user: dict = Depends(require_system_admin),
):
    """List access-request attempts that were auto-rejected before
    reaching the review queue, newest first (see
    access_request_blocked_attempts)."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    attempt_id,
                    attempted_email,
                    attempted_full_name,
                    reason,
                    remote_addr,
                    user_agent,
                    created_at
                FROM access_request_blocked_attempts
                ORDER BY created_at DESC
                """
            )

            return clean_rows(cur.fetchall())

    finally:
        conn.close()


@app.get("/api/admin/password-reset-log")
def admin_list_password_reset_log(
    admin_user: dict = Depends(require_system_admin),
):
    """List every password-reset attempt (requested/completed/invalid/
    inactive), newest first, joined to the account it targeted where one
    exists."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    l.log_id,
                    l.event_type,
                    l.email_provided,
                    u.username,
                    u.full_name,
                    l.remote_addr,
                    l.user_agent,
                    l.created_at
                FROM password_reset_log l
                LEFT JOIN users u
                    ON u.user_id = l.user_id
                ORDER BY l.created_at DESC
                """
            )

            return clean_rows(cur.fetchall())

    finally:
        conn.close()


def _set_user_account_status(
    user_id: int,
    new_status: str,
    admin_user: dict,
    block_self: bool,
):
    """Shared by deactivate/activate. Only role='user' accounts can be
    touched here - admin/system_admin/reviewer/expert accounts are
    managed directly in the database, not through this endpoint."""
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                "SELECT username, role FROM users WHERE user_id = %s",
                (user_id,),
            )

            target = cur.fetchone()

            if not target:
                raise HTTPException(status_code=404, detail="User not found")

            if target["role"] != "user":
                raise HTTPException(
                    status_code=400,
                    detail="Only regular users can be deactivated or reactivated here. "
                           "Administrator accounts are managed directly in the database.",
                )

            if block_self and target["username"] == admin_user.get("username"):
                raise HTTPException(
                    status_code=400,
                    detail="You cannot deactivate your own account",
                )

            cur.execute(
                """
                UPDATE users
                SET account_status = %s
                WHERE user_id = %s
                """,
                (new_status, user_id),
            )

            conn.commit()

            return {"status": "success"}

    finally:
        conn.close()


@app.post("/api/admin/users/{user_id}/deactivate")
def admin_deactivate_user(
    user_id: int,
    admin_user: dict = Depends(require_system_admin),
):
    """Set a regular user's account_status to DISABLED. Cannot target
    your own account."""
    return _set_user_account_status(user_id, "DISABLED", admin_user, block_self=True)


@app.post("/api/admin/users/{user_id}/activate")
def admin_activate_user(
    user_id: int,
    admin_user: dict = Depends(require_system_admin),
):
    """Set a regular user's account_status back to ACTIVE."""
    return _set_user_account_status(user_id, "ACTIVE", admin_user, block_self=False)


def _set_user_role(
    user_id: int,
    required_current_role: str,
    new_role: str,
    wrong_role_detail: str,
):
    """Shared by promote/demote. system_admin is never a valid
    required_current_role or new_role here - that tier is granted only via
    direct database access, never through the API."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                "SELECT role FROM users WHERE user_id = %s",
                (user_id,),
            )

            target = cur.fetchone()

            if not target:
                raise HTTPException(status_code=404, detail="User not found")

            if target["role"] != required_current_role:
                raise HTTPException(status_code=400, detail=wrong_role_detail)

            cur.execute(
                """
                UPDATE users
                SET role = %s
                WHERE user_id = %s
                """,
                (new_role, user_id),
            )

            conn.commit()

            return {"status": "success"}

    finally:
        conn.close()


@app.post("/api/admin/users/{user_id}/promote")
def admin_promote_user(
    user_id: int,
    admin_user: dict = Depends(require_system_admin),
):
    """Promote a role='user' account to 'admin'. 400 if the target isn't
    currently a plain user. Not called by the current frontend (users.html
    uses set-role below instead) - kept as a narrower alternative."""
    return _set_user_role(
        user_id,
        required_current_role="user",
        new_role="admin",
        wrong_role_detail="Only regular users can be promoted to admin here.",
    )


@app.post("/api/admin/users/{user_id}/demote")
def admin_demote_user(
    user_id: int,
    admin_user: dict = Depends(require_system_admin),
):
    """Demote a role='admin' account back to 'user'. 400 if the target
    isn't currently an admin."""
    return _set_user_role(
        user_id,
        required_current_role="admin",
        new_role="user",
        wrong_role_detail="Only admin accounts can be demoted to user here.",
    )


@app.post("/api/admin/users/{user_id}/set-role")
def admin_set_user_role(
    user_id: int,
    payload: dict = Body(...),
    admin_user: dict = Depends(require_system_admin),
):
    """Generalises promote/demote to the full set of API-assignable roles.
    system_admin is deliberately excluded - that tier stays DB-only, same
    convention _set_user_role already enforces above.
    """
    new_role = str(payload.get("role", "")).strip()

    if new_role not in {"user", "admin", "reviewer", "expert"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role FROM users WHERE user_id = %s", (user_id,))
            target = cur.fetchone()

            if not target:
                raise HTTPException(status_code=404, detail="User not found")

            if target["role"] == "system_admin":
                raise HTTPException(status_code=400, detail="system_admin accounts can't be changed here")

            cur.execute("UPDATE users SET role = %s WHERE user_id = %s", (new_role, user_id))

        conn.commit()
        return {"status": "success", "user_id": user_id, "role": new_role}

    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.post("/api/admin/users/{user_id}/delete")
def admin_delete_user(
    user_id: int,
    admin_user: dict = Depends(require_system_admin),
):
    """Permanently deletes a role='user' account, same DB-only restriction
    on other roles as deactivate/promote/demote/set-role above. Also clears
    the rows that carry a real foreign key to this user_id
    (password_reset_tokens, user_activation_tokens, password_reset_log) -
    everything else that references a user (site_feedback, slide_corrections,
    admin_audit_log, etc.) only stores a denormalized username/user_id with
    no FK, by design, so that history keeps reading correctly after the
    account is gone. Logged to admin_audit_log since, unlike deactivate,
    this can't be undone."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT username, role FROM users WHERE user_id = %s", (user_id,))
            target = cur.fetchone()

            if not target:
                raise HTTPException(status_code=404, detail="User not found")

            if target["role"] != "user":
                raise HTTPException(
                    status_code=400,
                    detail="Only regular users can be deleted here. "
                           "Administrator accounts are managed directly in the database.",
                )

            cur.execute("DELETE FROM password_reset_tokens WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM user_activation_tokens WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM password_reset_log WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))

            log_admin_action(conn, admin_user, "delete_user", target["username"])
            conn.commit()

            return {"status": "success"}

    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.get("/api/admin/settings")
def admin_get_settings(
    admin_user: dict = Depends(require_admin),
):
    """Return every system_settings row as a flat {setting_name:
    setting_value} dict (e.g. registration/activation notification
    templates and toggles)."""

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    setting_name,
                    setting_value
                FROM system_settings
                ORDER BY setting_name
                """
            )

            rows = cur.fetchall()

    finally:
        conn.close()

    settings = {}

    for row in rows:
        settings[row["setting_name"]] = row["setting_value"]

    return settings

@app.patch("/api/admin/settings")
def admin_update_settings(
    payload: dict = Body(...),
    admin_user: dict = Depends(require_admin),
):
    """Bulk-update system_settings from a {setting_name: setting_value}
    payload. Every key must already exist as a row - 400s on the first
    unknown setting name rather than creating new ones."""
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            for setting_name, setting_value in payload.items():

                cur.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM system_settings
                    WHERE setting_name = %s
                    """,
                    (setting_name,),
                )

                row = cur.fetchone()

                if row["n"] < 1:

                    raise HTTPException(
                        status_code=400,
                        detail=f"Unknown setting: {setting_name}"
                    )

                cur.execute(
                    """
                    UPDATE system_settings
                    SET
                        setting_value = %s,
                        updated_by = %s
                    WHERE setting_name = %s
                    """,
                    (
                        str(setting_value),
                        admin_user.get("username"),
                        setting_name,
                    ),
                )

        conn.commit()

    except Exception as exc:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )

    finally:
        conn.close()

    return {
        "status": "ok"
    }

def _build_corrections_report(
    status: Optional[str],
    feedback_source: Optional[str],
    feedback_type: Optional[str],
    slide_id: Optional[int],
    submitter_username: Optional[str],
    limit: int,
):
    """Shared filterable corrections listing behind both the admin and
    reviewer report endpoints - filtered rows plus summary counts grouped
    by source/type/status."""
    where = []
    params = []

    if status:
        where.append("status = %s")
        params.append(status)

    if feedback_source:
        where.append("feedback_source = %s")
        params.append(feedback_source)

    if feedback_type:
        where.append("feedback_type = %s")
        params.append(feedback_type)

    if slide_id:
        where.append("slide_id = %s")
        params.append(slide_id)

    if submitter_username:
        where.append("submitter_username LIKE %s")
        params.append("%" + submitter_username + "%")

    where_sql = ""
    if where:
        where_sql = "WHERE " + " AND ".join(where)

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS total_feedback,
                    SUM(status = 'new') AS new_feedback,
                    SUM(status = 'under_review') AS under_review_feedback,
                    SUM(status = 'accepted') AS accepted_feedback,
                    SUM(status = 'rejected') AS rejected_feedback,
                    SUM(status = 'resolved') AS resolved_feedback
                FROM slide_corrections
                {where_sql}
                """,
                params,
            )
            summary = clean_row(cur.fetchone())

            cur.execute(
                f"""
                SELECT
                    feedback_source,
                    COUNT(*) AS n
                FROM slide_corrections
                {where_sql}
                GROUP BY feedback_source
                ORDER BY n DESC, feedback_source
                """,
                params,
            )
            by_source = clean_rows(cur.fetchall())

            cur.execute(
                f"""
                SELECT
                    feedback_type,
                    COUNT(*) AS n
                FROM slide_corrections
                {where_sql}
                GROUP BY feedback_type
                ORDER BY n DESC, feedback_type
                """,
                params,
            )
            by_type = clean_rows(cur.fetchall())

            cur.execute(
                f"""
                SELECT
                    status,
                    COUNT(*) AS n
                FROM slide_corrections
                {where_sql}
                GROUP BY status
                ORDER BY n DESC, status
                """,
                params,
            )
            by_status = clean_rows(cur.fetchall())

            cur.execute(
                f"""
                SELECT
                    feedback_id,
                    slide_id,
                    slide_filename,
                    feedback_source,
                    feedback_type,
                    source_annotation_id,
                    source_legacy_curation_id,
                    current_value,
                    suggested_value,
                    feedback_text,
                    submitter_username,
                    submitter_email,
                    submitter_display_name,
                    submitter_role,
                    status,
                    admin_notes,
                    reviewed_by_username,
                    reviewed_at,
                    created_at,
                    updated_at
                FROM slide_corrections
                {where_sql}
                ORDER BY created_at DESC, feedback_id DESC
                LIMIT %s
                """,
                params + [limit],
            )
            rows = clean_rows(cur.fetchall())

    finally:
        conn.close()

    return {
        "status": "ok",
        "filters": {
            "status": status,
            "feedback_source": feedback_source,
            "feedback_type": feedback_type,
            "slide_id": slide_id,
            "submitter_username": submitter_username,
            "limit": limit,
        },
        "summary": summary,
        "by_source": by_source,
        "by_type": by_type,
        "by_status": by_status,
        "rows": rows,
    }


@app.get("/api/admin/corrections/report")
def corrections_report(
    status: Optional[str] = None,
    feedback_source: Optional[str] = None,
    feedback_type: Optional[str] = None,
    slide_id: Optional[int] = None,
    submitter_username: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    admin_user: dict = Depends(require_admin),
):
    """Admin corrections report/listing - see _build_corrections_report."""
    return _build_corrections_report(
        status, feedback_source, feedback_type, slide_id, submitter_username, limit,
    )


@app.get("/api/reviewer/corrections")
def reviewer_corrections_report(
    status: Optional[str] = None,
    feedback_source: Optional[str] = None,
    feedback_type: Optional[str] = None,
    slide_id: Optional[int] = None,
    submitter_username: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    user: dict = Depends(require_permission("corrections.view")),
):
    """Reviewer-role corrections report (permission-gated via
    corrections.view) - see _build_corrections_report."""
    return _build_corrections_report(
        status, feedback_source, feedback_type, slide_id, submitter_username, limit,
    )


@app.get("/api/admin/corrections/export.csv")
def corrections_export_csv(
    status: Optional[str] = None,
    feedback_source: Optional[str] = None,
    feedback_type: Optional[str] = None,
    slide_id: Optional[int] = None,
    submitter_username: Optional[str] = None,
    admin_user: dict = Depends(require_admin),
):
    """Same filters as the corrections report, but streamed as a CSV
    download (slide_corrections_report.csv) instead of JSON - no row
    limit."""
    where = []
    params = []

    if status:
        where.append("status = %s")
        params.append(status)

    if feedback_source:
        where.append("feedback_source = %s")
        params.append(feedback_source)

    if feedback_type:
        where.append("feedback_type = %s")
        params.append(feedback_type)

    if slide_id:
        where.append("slide_id = %s")
        params.append(slide_id)

    if submitter_username:
        where.append("submitter_username LIKE %s")
        params.append("%" + submitter_username + "%")

    where_sql = ""
    if where:
        where_sql = "WHERE " + " AND ".join(where)

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    feedback_id,
                    slide_id,
                    slide_filename,
                    feedback_source,
                    feedback_type,
                    source_annotation_id,
                    source_legacy_curation_id,
                    current_value,
                    suggested_value,
                    feedback_text,
                    submitter_username,
                    submitter_email,
                    submitter_display_name,
                    submitter_role,
                    status,
                    admin_notes,
                    reviewed_by_username,
                    reviewed_at,
                    remote_addr,
                    user_agent,
                    legacy_metadata_feedback_id,
                    created_at,
                    updated_at
                FROM slide_corrections
                {where_sql}
                ORDER BY created_at DESC, feedback_id DESC
                """,
                params,
            )
            rows = clean_rows(cur.fetchall())

    finally:
        conn.close()

    output = io.StringIO()

    fieldnames = [
        "feedback_id",
        "slide_id",
        "slide_filename",
        "feedback_source",
        "feedback_type",
        "source_annotation_id",
        "source_legacy_curation_id",
        "current_value",
        "suggested_value",
        "feedback_text",
        "submitter_username",
        "submitter_email",
        "submitter_display_name",
        "submitter_role",
        "status",
        "admin_notes",
        "reviewed_by_username",
        "reviewed_at",
        "remote_addr",
        "user_agent",
        "legacy_metadata_feedback_id",
        "created_at",
        "updated_at",
    ]

    def _csv_safe(value):
        # Prevents CSV formula injection: a value starting with =/+/-/@ is
        # interpreted as a formula by Excel/LibreOffice when the file is
        # opened, not shown as literal text - dangerous since every column
        # here can contain free text a site visitor submitted themselves
        # (feedback_text, suggested_value, submitter_display_name, etc.).
        # Prefixing with a leading apostrophe forces it to display as text.
        if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
            return "'" + value
        return value

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for row in rows:
        writer.writerow({field: _csv_safe(row.get(field)) for field in fieldnames})

    output.seek(0)

    filename = "slide_corrections_report.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )



@app.get("/api/filters/organs")
def filter_organs(user: dict = Depends(require_user)):
    """Distinct non-empty organ values actually in use in slide_metadata,
    for populating a search filter dropdown."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT organ
                FROM slide_metadata
                WHERE organ IS NOT NULL AND organ <> ''
                ORDER BY organ
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return {"organs": [row["organ"] for row in rows]}


@app.get("/api/filters/species")
def filter_species(user: dict = Depends(require_user)):
    """Distinct non-empty species values actually in use in
    slide_metadata, for populating a search filter dropdown."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT species
                FROM slide_metadata
                WHERE species IS NOT NULL AND species <> ''
                ORDER BY species
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return {"species": [row["species"] for row in rows]}


@app.get("/api/filters/stains")
def filter_stains(user: dict = Depends(require_user)):
    """Distinct stain values in use, canonicalized through
    stain_dictionary where a mapping exists, for a search filter
    dropdown."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT
                    COALESCE(sd.canonical_stain, sm.stain) AS stain
                FROM slide_metadata sm
                LEFT JOIN stain_dictionary sd
                    ON sd.original_stain = sm.stain
                WHERE sm.stain IS NOT NULL AND sm.stain <> ''
                ORDER BY stain
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return {"stains": [row["stain"] for row in rows]}


@app.get("/api/filters/tissues")
def filter_tissues(user: dict = Depends(require_user)):
    """Active canonical tissue values from tissue_dictionary, for a
    search filter dropdown."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT
                    COALESCE(canonical_tissue, tissue_name) AS tissue
                FROM tissue_dictionary
                WHERE active = 1
                ORDER BY tissue
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return {"tissues": [row["tissue"] for row in rows]}


@app.get("/api/contact-info")
def get_contact_info():
    """Public - just the one setting a visitor is meant to see (the real,
    purpose-specific contact_email, unlike CONTACT_NOTIFICATION_EMAIL/
    MAIL_FROM_CONTACT which stay server-side only). Lets the admin change
    the displayed address via the admin settings page without a redeploy.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT setting_value FROM system_settings WHERE setting_name = 'contact_email'"
            )
            row = cur.fetchone()
    finally:
        conn.close()

    return {"contact_email": (row["setting_value"] if row else None) or None}


@app.post("/api/contact")
def create_contact_message(payload: ContactMessageCreate, request: Request):
    """Public contact-form submission (no login required, unlike
    site-feedback below). Stored in contact_messages first, then emailed
    to CONTACT_NOTIFICATION_EMAIL as a courtesy notification - never
    storing or exposing that address to the browser. The email is
    best-effort (a broken mail server shouldn't surface as a confusing
    error to a visitor filling in a contact form), but a failed send no
    longer loses the message itself: it stays in the database
    (email_sent_at left NULL) for an admin to find via the SQL console
    regardless of whether the notification ever arrived.
    """
    name = payload.name.strip()
    email = payload.email.strip()
    message_text = payload.message.strip()

    if not name or not email or not message_text:
        raise HTTPException(status_code=400, detail="Name, email, and message are all required")

    remote_addr = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contact_messages (
                    name, email, message_text, remote_addr, user_agent
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (name, email, message_text, remote_addr, user_agent),
            )
            message_id = cur.lastrowid
            conn.commit()

            to_address = os.getenv("CONTACT_NOTIFICATION_EMAIL")
            if to_address:
                body = (
                    f"New contact form submission from the slide catalogue.\n\n"
                    f"Name: {name}\n"
                    f"Email: {email}\n"
                    f"Remote address: {remote_addr or 'unknown'}\n\n"
                    f"Message:\n{message_text}"
                )
                try:
                    send_email(
                        to_address,
                        f"Catalogue contact form: {name}",
                        body,
                        from_override=os.getenv("MAIL_FROM_CONTACT"),
                        reply_to=email,
                    )
                    cur.execute(
                        "UPDATE contact_messages SET email_sent_at = NOW() WHERE message_id = %s",
                        (message_id,),
                    )
                    conn.commit()
                except Exception as exc:
                    print("Failed to send contact form email (message safely stored, id", message_id, "):", exc)
    finally:
        conn.close()

    return {"status": "ok", "message": "Thank you - your message has been sent."}


@app.post("/api/site-feedback")
def create_site_feedback(
    request: Request,
    payload: dict = Body(...),
    user: dict | None = Depends(get_optional_user),
):
    """General feedback about the site itself - not tied to any slide.

    Separate from slide_corrections (metadata corrections), which always
    needs a slide_id - this is for things like "the search filters are
    confusing" or "please add X feature" from anywhere on the site.

    Open to anonymous visitors as well as logged-in users (see
    get_optional_user) - submitter_username/email/etc. are just NULL for
    an anonymous submission, not required.
    """

    feedback_text = str(payload.get("feedback_text", "")).strip()
    page_url = str(payload.get("page_url", "")).strip() or None

    if not feedback_text:
        raise HTTPException(status_code=400, detail="Feedback text is required")
    if len(feedback_text) > 10000:
        raise HTTPException(status_code=400, detail="Feedback text is too long")
    if len(page_url or "") > 500:
        page_url = page_url[:500]

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            remote_addr = None
            if request.client:
                remote_addr = request.client.host

            user_agent = request.headers.get("user-agent", "")

            cur.execute(
                """
                INSERT INTO site_feedback (
                    feedback_text,
                    page_url,
                    submitter_username,
                    submitter_email,
                    submitter_display_name,
                    submitter_role,
                    remote_addr,
                    user_agent
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    feedback_text,
                    page_url,
                    user.get("username") if user else None,
                    user.get("email") if user else None,
                    user.get("display_name") if user else None,
                    user.get("role") if user else None,
                    remote_addr,
                    user_agent[:500] if user_agent else None,
                ),
            )

            feedback_id = cur.lastrowid

        conn.commit()

        return {
            "status": "ok",
            "feedback_id": feedback_id,
            "message": "Feedback submitted, thank you.",
        }

    except HTTPException:
        raise

    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        conn.close()


@app.get("/api/admin/site-feedback/report")
def admin_site_feedback_report(
    status: Optional[str] = None,
    admin_user: dict = Depends(require_admin),
):
    """List site_feedback rows, optionally filtered by status, newest
    first."""
    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            where = []
            params = []

            if status:
                where.append("status = %s")
                params.append(status)

            where_clause = ("WHERE " + " AND ".join(where)) if where else ""

            cur.execute(
                f"""
                SELECT
                    feedback_id,
                    feedback_text,
                    page_url,
                    submitter_username,
                    submitter_email,
                    submitter_display_name,
                    submitter_role,
                    status,
                    admin_notes,
                    reviewed_by_username,
                    reviewed_at,
                    created_at
                FROM site_feedback
                {where_clause}
                ORDER BY created_at DESC
                """,
                params,
            )

            rows = clean_rows(cur.fetchall())

    finally:
        conn.close()

    return {"rows": rows}


@app.patch("/api/admin/site-feedback/{feedback_id}/review")
def admin_update_site_feedback_review(
    feedback_id: int,
    payload: dict = Body(...),
    admin_user: dict = Depends(require_admin),
):
    """Update a site_feedback row's review status/notes. Unlike
    slide_corrections, there's no self-review guard, no correction
    actions log, and no thank-you email here - just a status/notes
    update."""
    status = str(payload.get("status", "")).strip()
    admin_notes = payload.get("admin_notes")

    allowed_status = {"new", "under_review", "accepted", "rejected", "resolved"}

    if status not in allowed_status:
        raise HTTPException(status_code=400, detail="Invalid feedback status")

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT feedback_id FROM site_feedback WHERE feedback_id = %s",
                (feedback_id,),
            )

            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Feedback not found")

            cur.execute(
                """
                UPDATE site_feedback
                SET
                    status = %s,
                    admin_notes = %s,
                    reviewed_by_username = %s,
                    reviewed_at = NOW()
                WHERE feedback_id = %s
                """,
                (
                    status,
                    admin_notes,
                    admin_user.get("username"),
                    feedback_id,
                ),
            )

        conn.commit()

        return {
            "status": "ok",
            "feedback_id": feedback_id,
            "new_status": status,
        }

    except HTTPException:
        raise

    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        conn.close()
