import os
import smtplib
from email.message import EmailMessage


def send_email(to_address: str, subject: str, body: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_address = os.getenv("SMTP_FROM") or username

    if not host or not from_address:
        raise RuntimeError("SMTP is not configured (SMTP_HOST/SMTP_FROM missing)")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = to_address
    message.set_content(body)

    with smtplib.SMTP(host, port, timeout=10) as server:
        server.starttls()
        if username:
            server.login(username, password)
        server.send_message(message)
