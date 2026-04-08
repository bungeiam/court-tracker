import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)


SENDER_NAME = os.getenv("COURT_TRACKER_SENDER_NAME", "")
SENDER_EMAIL = os.getenv("COURT_TRACKER_SENDER_EMAIL", "")
SENDER_PHONE = os.getenv("COURT_TRACKER_SENDER_PHONE", "")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Court Tracker")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"