import os

import pymysql
from fastapi import HTTPException, Request


def _connect():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "catalogue_mariadb"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def user_has_permission(conn, role, permission_key):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM role_permissions WHERE role = %s AND permission_key = %s",
            (role, permission_key),
        )
        return cur.fetchone() is not None


def require_permission(permission_key):
    """Dependency factory driving reviewer/expert authorization from the
    role_permissions table, rather than hardcoding role names in Python -
    unlike require_admin/require_system_admin in main.py, which stay as-is
    for existing admin-only endpoints.
    """

    def dependency(request: Request):
        from app.main import require_user  # local import - avoids a circular

        user = require_user(request)

        conn = _connect()
        try:
            if not user_has_permission(conn, user.get("role"), permission_key):
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing permission: {permission_key}",
                )
        finally:
            conn.close()

        return user

    return dependency
