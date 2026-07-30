"""Audit trail for system_admin-only mutating actions (POST /api/admin/backup,
POST /api/admin/sql, POST /api/admin/users/{id}/delete) - see
migrations/..._add_admin_audit_log.sql. Callers decide what counts as a
mutation worth logging (e.g. main.py only calls this from the non-SELECT
branch of the SQL console); this module just records it.
"""


def log_admin_action(conn, user, action, detail=None):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO admin_audit_log (user_id, username, action, detail) "
            "VALUES (%s, %s, %s, %s)",
            (user.get("user_id"), user.get("username"), action, detail),
        )
