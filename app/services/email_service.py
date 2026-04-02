import smtplib
from email.message import EmailMessage

from app.config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_USE_TLS,
)


def send_email(to_email: str, subject: str, body: str) -> None:
    if not SMTP_HOST:
        raise ValueError("SMTP_HOST puuttuu")
    if not SMTP_PORT:
        raise ValueError("SMTP_PORT puuttuu")
    if not SMTP_FROM_EMAIL:
        raise ValueError("SMTP_FROM_EMAIL puuttuu")
    if not to_email:
        raise ValueError("Vastaanottajan sähköpostiosoite puuttuu")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()

        if SMTP_USE_TLS:
            server.starttls()
            server.ehlo()

        if SMTP_USERNAME:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)

        server.send_message(msg)