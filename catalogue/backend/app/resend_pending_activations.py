#!/usr/bin/env python3
"""Resend the activation invite email for PENDING_ACTIVATION accounts -
e.g. accounts approved while the SMTP relay was misconfigured (see
mailer.py's login-fix) whose original invite email silently failed
(send_activation_invite() is deliberately best-effort - a broken mail
server must not break the approval itself, so the account/token were
created successfully even though no email went out).

Regenerates the activation token if the existing one has already expired
or been used; otherwise reuses the existing token unchanged, so a link a
user already has open/bookmarked keeps working.

Run inside catalogue_backend, same as sync_manual_thumbnails.py (needs
the app's own DB credentials and SMTP_* environment). Must be invoked as
a module (-m), not a file path, so the `app.main` import resolves the
same way it does under the container's WORKDIR /app:
  docker compose exec catalogue_backend python3 -m app.resend_pending_activations
      (dry run - lists who would be emailed, sends nothing)
  docker compose exec catalogue_backend python3 -m app.resend_pending_activations --execute
      (actually sends)
  docker compose exec catalogue_backend python3 -m app.resend_pending_activations --execute --user-id 123
      (only that one account)
"""

import argparse
import os
import uuid
from datetime import datetime, timedelta

from app.main import get_db_connection, send_activation_invite


def find_pending(cur, user_id=None):
    query = """
        SELECT
            u.user_id, u.username, u.email, u.full_name, u.account_status,
            t.activation_token, t.expires_at, t.used_at
        FROM users u
        LEFT JOIN user_activation_tokens t ON t.user_id = u.user_id
        WHERE u.account_status = 'PENDING_ACTIVATION'
    """
    params = []
    if user_id is not None:
        query += " AND u.user_id = %s"
        params.append(user_id)
    query += " ORDER BY u.user_id"
    cur.execute(query, params)
    return cur.fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="Actually send emails (default: dry run, sends nothing)")
    parser.add_argument("--user-id", type=int, help="Only process this one user_id")
    args = parser.parse_args()

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            rows = find_pending(cur, args.user_id)

            if not rows:
                print("No PENDING_ACTIVATION accounts found.")
                return

            for row in rows:
                now = datetime.utcnow()
                needs_new_token = (
                    row["activation_token"] is None
                    or row["used_at"] is not None
                    or row["expires_at"] is None
                    or row["expires_at"] < now
                )

                action = "will generate a new token" if needs_new_token else "will reuse existing token"
                print(f"user_id={row['user_id']} username={row['username']} email={row['email']} - {action}")

                if not args.execute:
                    continue

                if needs_new_token:
                    token = str(uuid.uuid4())
                    expires_at = now + timedelta(days=7)
                    cur.execute(
                        "DELETE FROM user_activation_tokens WHERE user_id = %s",
                        (row["user_id"],),
                    )
                    cur.execute(
                        """
                        INSERT INTO user_activation_tokens (user_id, activation_token, expires_at)
                        VALUES (%s, %s, %s)
                        """,
                        (row["user_id"], token, expires_at),
                    )
                    conn.commit()
                else:
                    token = row["activation_token"]
                    expires_at = row["expires_at"]

                activation_link = (
                    os.getenv("APP_BASE_URL", "http://localhost:8080")
                    + "/activate.html?token="
                    + token
                )

                send_activation_invite(
                    cur,
                    {
                        "full_name": row["full_name"],
                        "username": row["username"],
                        "email": row["email"],
                        "activation_link": activation_link,
                        "expires_at": expires_at.strftime("%Y-%m-%d %H:%M UTC"),
                    },
                )
                print(f"  sent to {row['email']}")

            if not args.execute:
                print("\nDry run - nothing was sent. Re-run with --execute to actually send.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
