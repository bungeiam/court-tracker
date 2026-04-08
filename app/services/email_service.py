# app/services/email_service.py
import smtplib
from email.message import EmailMessage

from app.config import (
    SENDER_EMAIL,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_USE_TLS,
)


def _validate_email_settings() -> None:
    if not SENDER_EMAIL:
        raise ValueError(
            "Lähetys estetty: lähettäjän sähköpostiosoite puuttuu "
            "(COURT_TRACKER_SENDER_EMAIL)."
        )

    if not SMTP_HOST:
        raise ValueError(
            "Lähetys estetty: SMTP-palvelimen osoite puuttuu (SMTP_HOST)."
        )

    if not SMTP_USERNAME:
        raise ValueError(
            "Lähetys estetty: SMTP-käyttäjätunnus puuttuu (SMTP_USERNAME)."
        )

    if not SMTP_PASSWORD:
        raise ValueError(
            "Lähetys estetty: SMTP-salasana puuttuu (SMTP_PASSWORD)."
        )


def send_email(to_email: str, subject: str, body: str) -> None:
    _validate_email_settings()

    if not SMTP_PORT:
        raise ValueError("Lähetys estetty: SMTP-portti puuttuu (SMTP_PORT).")

    if not to_email:
        raise ValueError("Lähetys estetty: vastaanottajan sähköpostiosoite puuttuu.")

    from_email = SMTP_FROM_EMAIL or SENDER_EMAIL

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{from_email}>"
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()

        if SMTP_USE_TLS:
            server.starttls()
            server.ehlo()

        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)