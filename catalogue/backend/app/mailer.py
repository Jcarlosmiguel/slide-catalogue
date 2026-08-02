import os
import smtplib
from email.message import EmailMessage


def send_email(
    to_address: str,
    subject: str,
    body: str,
    from_override: str | None = None,
    reply_to: str | None = None,
) -> None:
    """from_override lets a caller present a purpose-specific display name
    (e.g. "Catalogue Registration" <real@address>) without changing the
    actual envelope address/credentials - useful while real per-purpose
    mailboxes don't exist yet: all mail still goes through the one
    configured relay account, just labelled differently per purpose. Once
    real mailboxes exist, point the relevant MAIL_FROM_* env var at the
    real address instead - no code change needed.

    reply_to lets a caller (e.g. the public contact form) set a Reply-To
    distinct from From - so hitting "reply" in a mail client goes straight
    to a form submitter's own address, not back to the relay identity.
    """
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_address = from_override or os.getenv("SMTP_FROM") or username

    if not host or not from_address:
        raise RuntimeError("SMTP is not configured (SMTP_HOST/SMTP_FROM missing)")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = to_address
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)

    with smtplib.SMTP(host, port, timeout=10) as server:
        server.starttls()
        if username:
            server.login(username, password)
        server.send_message(message)
