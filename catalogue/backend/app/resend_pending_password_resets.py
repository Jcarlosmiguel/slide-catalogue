#!/usr/bin/env python3
"""Resend a user's most recent password-reset email - e.g. one sent while
the SMTP relay was misconfigured (see mailer.py's login-fix) that silently
failed (send_password_reset_email() is deliberately best-effort - a broken
mail server must not break the reset request itself, so the token was
created successfully even though no email went out).

Unlike resend_pending_activations.py, this is NOT a "resend to everyone
pending" sweep: a password reset is a per-request event, not a persistent
account state - request_password_reset() never deletes or dedupes
previous requests, so a user with several old, expired, abandoned reset
attempts is completely normal and NOT something to bulk-resend. This
script only ever targets one specific user, found by --email or
--user-id, and refuses to --execute without one. Reset tokens also expire
in 2 hours (not 7 days like activation), so by the time anyone reports a
problem the existing token has very likely already expired - a fresh one
is generated whenever the found token is missing/used/expired, same
regenerate-if-needed logic as resend_pending_activations.py otherwise.

Run inside catalogue_backend, same as resend_pending_activations.py (needs
the app's own DB credentials and SMTP_* environment). Must be invoked as
a module (-m), not a file path, so the `app.main` import resolves the
same way it does under the container's WORKDIR /app:
  docker compose exec catalogue_backend python3 -m app.resend_pending_password_resets --email user@example.com
      (dry run - shows what would happen, sends nothing)
  docker compose exec catalogue_backend python3 -m app.resend_pending_password_resets --email user@example.com --execute
      (actually sends)
  docker compose exec catalogue_backend python3 -m app.resend_pending_password_resets --user-id 123 --execute
      (target by user_id instead of email)
"""

import argparse
import os
import uuid
from datetime import datetime, timedelta

from app.main import get_db_connection, send_password_reset_email


def find_latest_reset(cur, user_id=None, email=None):
    """The most recent password_reset_tokens row for the targeted user, if
    any - ORDER BY expires_at DESC is a safe proxy for request recency
    here, since every row gets the same fixed 2-hour offset from its own
    request time. Returns None if the user has never requested a reset at
    all, which the caller should treat as an error, not something to
    silently create a token for - only request_password_reset() (the real
    "forgot password" flow) should ever originate a first request."""
    query = """
        SELECT
            u.user_id, u.username, u.email, u.full_name, u.account_status,
            t.reset_token, t.expires_at, t.used_at
        FROM users u
        LEFT JOIN password_reset_tokens t ON t.user_id = u.user_id
        WHERE 1=1
    """
    params = []
    if user_id is not None:
        query += " AND u.user_id = %s"
        params.append(user_id)
    if email is not None:
        query += " AND u.email = %s"
        params.append(email)
    query += " ORDER BY t.expires_at DESC LIMIT 1"
    cur.execute(query, params)
    return cur.fetchone()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="Actually send the email (default: dry run, sends nothing)")
    parser.add_argument("--user-id", type=int, help="Target this user_id")
    parser.add_argument("--email", help="Target this user's email address")
    args = parser.parse_args()

    if not args.user_id and not args.email:
        parser.error("--user-id or --email is required - this never bulk-resends to everyone with a pending reset")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            row = find_latest_reset(cur, args.user_id, args.email)

            if row is None:
                print("No matching user found.")
                return

            if row["account_status"] != "ACTIVE":
                print(f"user_id={row['user_id']} username={row['username']} - account_status is "
                      f"{row['account_status']}, not ACTIVE - request_password_reset() would refuse "
                      f"this too, refusing to resend.")
                return

            now = datetime.utcnow()
            needs_new_token = (
                row["reset_token"] is None
                or row["used_at"] is not None
                or row["expires_at"] is None
                or row["expires_at"] < now
            )

            action = "will generate a new token" if needs_new_token else "will reuse existing token"
            print(f"user_id={row['user_id']} username={row['username']} email={row['email']} - {action}")

            if not args.execute:
                print("\nDry run - nothing was sent. Re-run with --execute to actually send.")
                return

            if needs_new_token:
                token = str(uuid.uuid4())
                expires_at = now + timedelta(hours=2)
                cur.execute(
                    """
                    INSERT INTO password_reset_tokens (user_id, reset_token, expires_at)
                    VALUES (%s, %s, %s)
                    """,
                    (row["user_id"], token, expires_at),
                )
                conn.commit()
            else:
                token = row["reset_token"]
                expires_at = row["expires_at"]

            reset_link = (
                os.getenv("APP_BASE_URL", "http://localhost:8080")
                + "/reset-password.html?token="
                + token
            )

            send_password_reset_email(
                cur,
                {
                    "full_name": row["full_name"],
                    "username": row["username"],
                    "email": row["email"],
                    "reset_link": reset_link,
                    "expires_at": expires_at.strftime("%Y-%m-%d %H:%M UTC"),
                },
            )
            print(f"  sent to {row['email']}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
