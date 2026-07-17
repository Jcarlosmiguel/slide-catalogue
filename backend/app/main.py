import os
import json
import csv
import io
import hmac
import time
import base64
import uuid

import hashlib
from datetime import (
    date,
    datetime,
    timedelta,
)
from argon2 import PasswordHasher
from decimal import Decimal
from typing import Any, Optional
from pydantic import BaseModel
import pymysql
from fastapi import FastAPI, HTTPException, Query, Request, Response, Body, Depends
from fastapi.responses import StreamingResponse


app = FastAPI(
    title="MVLS Virtual Microscopy Catalogue API",
    root_path=os.getenv("APP_ROOT_PATH", "")
)

# ---------------------------------------------------------------------
# Prototype local authentication
# ---------------------------------------------------------------------

SESSION_COOKIE_NAME = "mvls_session"
SESSION_DURATION_SECONDS = 12 * 60 * 60


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def get_session_secret() -> str:
    return os.getenv("APP_SESSION_SECRET", "replace-this-with-a-long-random-secret")


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

def configured_users():
    return {
        os.getenv("GENERAL_USER_USERNAME", "general_user"): {
            "username": os.getenv("GENERAL_USER_USERNAME", "general_user"),
            "password": os.getenv("GENERAL_USER_PASSWORD", "change-this-general-password"),
            "email": os.getenv("GENERAL_USER_EMAIL", "general_user@example.local"),
            "display_name": "General user",
            "role": "general_user",
        },
        os.getenv("POWER_USER_USERNAME", "power_user"): {
            "username": os.getenv("POWER_USER_USERNAME", "power_user"),
            "password": os.getenv("POWER_USER_PASSWORD", "change-this-power-password"),
            "email": os.getenv("POWER_USER_EMAIL", "power_user@example.local"),
            "display_name": "Power user",
            "role": "power_user",
        },
        os.getenv("ADMIN_USER_USERNAME", "admin"): {
            "username": os.getenv("ADMIN_USER_USERNAME", "admin"),
            "password": os.getenv("ADMIN_USER_PASSWORD", "change-this-admin-password"),
            "email": os.getenv("ADMIN_USER_EMAIL", "admin@example.local"),
            "display_name": "Administrator",
            "role": "admin",
        },
    }


def require_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE_NAME)

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = verify_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return payload



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

@app.post("/api/login")
def login(response: Response, payload: dict = Body(...)):
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

            user = cur.fetchone()

        if not user:

            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )

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

            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )

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
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"status": "ok"}


@app.get("/api/me")
def me(user: dict = Depends(require_user)):
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
            "path_prefix": os.getenv("SHARE_ROOT_WINDOWS", r"\\mvls-share\virtual-microscopy"),
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
    return {
        "status": "ok",
        "service": "mvls-catalogue-backend"
    }


@app.get("/api/db-health")
def db_health():
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
        return {
            "status": "error",
            "detail": str(exc)
        }


@app.get("/api/thumbnail-paths/{slide_id}")
def thumbnail_paths(slide_id: int):
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

class ActivationRequest(BaseModel):
    token: str
    password: str


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
                    cur.execute(
                        "SELECT user_id FROM users WHERE username = %s AND user_id != %s",
                        (new_username, current_row["user_id"]),
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
                        "SELECT user_id FROM users WHERE email = %s AND user_id != %s",
                        (new_email, current_row["user_id"]),
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
            if len(payload.new_password) < 8:
                raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
            if not any(char.isupper() for char in payload.new_password):
                raise HTTPException(status_code=400, detail="Password must include an uppercase letter")
            if not any(char.islower() for char in payload.new_password):
                raise HTTPException(status_code=400, detail="Password must include a lowercase letter")
            if not any(char.isdigit() for char in payload.new_password):
                raise HTTPException(status_code=400, detail="Password must include a number")
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


@app.post("/api/access-request")
def create_access_request(request: AccessRequestCreate):

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

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

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    t.user_id,
                    t.used_at,
                    t.expires_at
                FROM user_activation_tokens t
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

            return {
                "status": "success",
                "message": "Account activated"
            }

    finally:
        conn.close()

@app.get("/api/featured-slides")
def featured_slides():

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
                LIMIT 4
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
    organ: Optional[str] = None,
    species: Optional[str] = None,
    stain: Optional[str] = None,
    tissue: Optional[str] = None,
    has_david_notes: Optional[bool] = None,
    active_only: bool = True,
    order_by: str = Query("slide_id"),
    order_dir: str = Query("asc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    where = []
    params = []

    if active_only:
        where.append("s.asset_status = 'ACTIVE'")


    if slide_id is not None:
        where.append("s.slide_id = %s")
        params.append(slide_id)


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
                    FROM v_slide_david_notes vdn
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

    if has_david_notes is True:
        where.append("EXISTS (SELECT 1 FROM slide_david_annotations sda WHERE sda.slide_id = s.slide_id)")
    elif has_david_notes is False:
        where.append("NOT EXISTS (SELECT 1 FROM slide_david_annotations sda WHERE sda.slide_id = s.slide_id)")

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
                WHERE sa.slide_id = s.slide_id
            ) AS has_slide_annotations,

            EXISTS (
                SELECT 1
                FROM slide_tissue_annotations sta
                WHERE sta.slide_id = s.slide_id
            ) AS has_tissue_annotations,

            EXISTS (
                SELECT 1
                FROM slide_david_annotations sda
                WHERE sda.slide_id = s.slide_id
            ) AS has_david_notes

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




@app.post("/api/slides/{slide_id}/metadata-feedback")
def create_metadata_feedback(
    slide_id: int,
    request: Request,
    payload: dict = Body(...),
    user: dict = Depends(require_user),
):
    feedback_type = str(payload.get("feedback_type", "general_comment")).strip()
    current_value = payload.get("current_value")
    suggested_value = payload.get("suggested_value")
    feedback_text = str(payload.get("feedback_text", "")).strip()

    allowed_types = {"organ", "tissue", "species", "stain", "general_comment"}

    if feedback_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid feedback type")

    if not feedback_text:
        raise HTTPException(status_code=400, detail="Feedback text is required")

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
                INSERT INTO slide_feedback (
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


@app.get("/api/slides/{slide_id}")
def get_slide(slide_id: int, os_key: str = Query("linux", alias="os"), user: dict = Depends(require_user)):
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
                WHERE slide_id = %s
                ORDER BY annotation_id
                """,
                (slide_id,),
            )
            annotations = cur.fetchall()

            cur.execute(
                """
                SELECT
                    david_record_id,
                    annotation_title,
                    note_text,
                    confidence_score,
                    reconciliation_method,
                    reconciliation_notes
                FROM v_slide_david_notes
                WHERE slide_id = %s
                ORDER BY david_record_id
                """,
                (slide_id,),
            )
            david_notes = cur.fetchall()

    finally:
        conn.close()

    core = clean_row(core)
    tissues = clean_rows(tissues)
    annotations = clean_rows(annotations)
    david_notes = clean_rows(david_notes)

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
        "david_notes": david_notes,
    }




@app.get("/api/admin/dictionaries/{dictionary_name}")
def admin_dictionary_values(
    dictionary_name: str,
    admin_user: dict = Depends(require_admin),
):
    dictionary_name = dictionary_name.lower()

    if dictionary_name not in {"organ", "species", "stain"}:
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
                        stain_family,
                        normalisation_status
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


@app.patch("/api/admin/feedback/{feedback_id}/review")
def admin_update_feedback_review(
    feedback_id: int,
    payload: dict = Body(...),
    admin_user: dict = Depends(require_admin),
):
    status = str(payload.get("status", "")).strip()
    admin_notes = payload.get("admin_notes")

    allowed_status = {"new", "under_review", "accepted", "rejected", "resolved"}

    if status not in allowed_status:
        raise HTTPException(status_code=400, detail="Invalid feedback status")

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT feedback_id, slide_id, status
                FROM slide_feedback
                WHERE feedback_id = %s
                """,
                (feedback_id,),
            )
            feedback = cur.fetchone()

            if feedback is None:
                raise HTTPException(status_code=404, detail="Feedback not found")

            old_status = feedback["status"]

            cur.execute(
                """
                UPDATE slide_feedback
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

            cur.execute(
                """
                INSERT INTO slide_feedback_actions (
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
                    feedback_id,
                    feedback["slide_id"],
                    old_status,
                    status,
                    admin_notes,
                    admin_user.get("username"),
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


@app.post("/api/admin/feedback/{feedback_id}/apply-metadata-correction")
def admin_apply_metadata_correction(
    feedback_id: int,
    payload: dict = Body(...),
    admin_user: dict = Depends(require_admin),
):
    field_name = str(payload.get("field_name", "")).strip().lower()
    new_value = str(payload.get("new_value", "")).strip()
    admin_notes = payload.get("admin_notes")

    allowed_fields = {
        "organ": "organ",
        "species": "species",
        "stain": "stain",
    }

    if field_name not in allowed_fields:
        raise HTTPException(status_code=400, detail="Only organ, species and stain can be corrected here")

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
                    status
                FROM slide_feedback
                WHERE feedback_id = %s
                """,
                (feedback_id,),
            )
            feedback = cur.fetchone()

            if feedback is None:
                raise HTTPException(status_code=404, detail="Feedback not found")

            if feedback["feedback_source"] != "metadata":
                raise HTTPException(status_code=400, detail="Only metadata feedback can be applied here")

            if feedback["feedback_type"] != field_name:
                raise HTTPException(
                    status_code=400,
                    detail="Feedback type does not match requested metadata field",
                )

            slide_id = feedback["slide_id"]

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

            column_name = allowed_fields[field_name]

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
                UPDATE slide_feedback
                SET
                    status = 'accepted',
                    admin_notes = %s,
                    reviewed_by_username = %s,
                    reviewed_at = NOW()
                WHERE feedback_id = %s
                """,
                (
                    admin_notes,
                    admin_user.get("username"),
                    feedback_id,
                ),
            )

            cur.execute(
                """
                INSERT INTO slide_feedback_actions (
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
                    feedback_id,
                    slide_id,
                    field_name,
                    old_value,
                    new_value,
                    admin_notes,
                    admin_user.get("username"),
                ),
            )

        conn.commit()

        return {
            "status": "ok",
            "feedback_id": feedback_id,
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

@app.get("/api/admin/settings")
def admin_get_settings(
    admin_user: dict = Depends(require_admin),
):

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

@app.get("/api/admin/feedback/report")
def feedback_report(
    status: Optional[str] = None,
    feedback_source: Optional[str] = None,
    feedback_type: Optional[str] = None,
    slide_id: Optional[int] = None,
    submitter_username: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    admin_user: dict = Depends(require_admin),
):
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
                FROM slide_feedback
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
                FROM slide_feedback
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
                FROM slide_feedback
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
                FROM slide_feedback
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
                    source_david_record_id,
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
                FROM slide_feedback
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


@app.get("/api/admin/feedback/export.csv")
def feedback_export_csv(
    status: Optional[str] = None,
    feedback_source: Optional[str] = None,
    feedback_type: Optional[str] = None,
    slide_id: Optional[int] = None,
    submitter_username: Optional[str] = None,
    admin_user: dict = Depends(require_admin),
):
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
                    source_david_record_id,
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
                FROM slide_feedback
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
        "source_david_record_id",
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

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for row in rows:
        writer.writerow({field: row.get(field) for field in fieldnames})

    output.seek(0)

    filename = "mvls_slide_feedback_report.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )



@app.get("/api/filters/organs")
def filter_organs(user: dict = Depends(require_user)):
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
