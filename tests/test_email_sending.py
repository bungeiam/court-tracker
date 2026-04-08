# tests/test_email_sending.py
from app.services import email_service


class DummySMTP:
    last_instance = None

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.ehlo_called = 0
        self.starttls_called = False
        self.login_args = None
        self.sent_message = None
        DummySMTP.last_instance = self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        self.ehlo_called += 1

    def starttls(self):
        self.starttls_called = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, msg):
        self.sent_message = msg


def _apply_valid_config(monkeypatch):
    monkeypatch.setattr(email_service, "SENDER_EMAIL", "sender@example.com")
    monkeypatch.setattr(email_service, "SMTP_HOST", "sandbox.smtp.mailtrap.io")
    monkeypatch.setattr(email_service, "SMTP_PORT", 587)
    monkeypatch.setattr(email_service, "SMTP_USERNAME", "mailtrap-user")
    monkeypatch.setattr(email_service, "SMTP_PASSWORD", "mailtrap-pass")
    monkeypatch.setattr(email_service, "SMTP_FROM_EMAIL", "")
    monkeypatch.setattr(email_service, "SMTP_FROM_NAME", "Court Tracker")
    monkeypatch.setattr(email_service, "SMTP_USE_TLS", True)


def test_send_email_succeeds_when_config_is_valid(monkeypatch):
    _apply_valid_config(monkeypatch)
    monkeypatch.setattr(email_service.smtplib, "SMTP", DummySMTP)

    email_service.send_email(
        to_email="recipient@example.com",
        subject="Test subject",
        body="Test body",
    )

    smtp_instance = DummySMTP.last_instance
    assert smtp_instance is not None
    assert smtp_instance.host == "sandbox.smtp.mailtrap.io"
    assert smtp_instance.port == 587
    assert smtp_instance.starttls_called is True
    assert smtp_instance.login_args == ("mailtrap-user", "mailtrap-pass")
    assert smtp_instance.sent_message is not None
    assert smtp_instance.sent_message["To"] == "recipient@example.com"
    assert smtp_instance.sent_message["From"] == "Court Tracker <sender@example.com>"
    assert smtp_instance.sent_message["Subject"] == "Test subject"


def test_send_email_fails_when_sender_email_is_missing(monkeypatch):
    _apply_valid_config(monkeypatch)
    monkeypatch.setattr(email_service, "SENDER_EMAIL", "")

    try:
        email_service.send_email(
            to_email="recipient@example.com",
            subject="Test subject",
            body="Test body",
        )
        assert False, "Expected ValueError when SENDER_EMAIL is missing"
    except ValueError as exc:
        assert "COURT_TRACKER_SENDER_EMAIL" in str(exc)


def test_send_email_fails_when_smtp_settings_are_missing(monkeypatch):
    _apply_valid_config(monkeypatch)
    monkeypatch.setattr(email_service, "SMTP_HOST", "")

    try:
        email_service.send_email(
            to_email="recipient@example.com",
            subject="Test subject",
            body="Test body",
        )
        assert False, "Expected ValueError when SMTP settings are missing"
    except ValueError as exc:
        assert "SMTP_HOST" in str(exc)