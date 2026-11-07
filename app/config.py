import os
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent

APP_ENV = os.getenv("APP_ENV", "development")
OTP_SECRET = os.getenv("OTP_SECRET", "dev-secret-change-me")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
EMAIL_API_KEY = os.getenv("EMAIL_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "Madhav Hegde Campaign <otp@mail.ibrag.co.in>")
EMAIL_REPLY_TO = os.getenv("EMAIL_REPLY_TO", "docmadhavhegde@gmail.com")
LOOKUP_MODE = os.getenv("LOOKUP_MODE", "direct").strip().lower()  # "direct" | "otp" | "show"
if LOOKUP_MODE not in ("direct", "otp", "show"):
    LOOKUP_MODE = "direct"
INTERAKT_API_KEY = os.getenv("INTERAKT_API_KEY", "").strip()
WA_TEMPLATE_MEMBER_ID = os.getenv("WA_TEMPLATE_MEMBER_ID", "").strip()
ENABLED_ADDONS = [a.strip() for a in os.getenv("ENABLED_ADDONS", "").split(",") if a.strip()]

OTP_TTL_MIN = 5
OTP_MAX_ATTEMPTS = 3
OTP_PER_MEMBER_PER_HOUR = 3
LOOKUPS_PER_IP_PER_HOUR = 10
ID_SENDS_PER_MEMBER_PER_HOUR = 3


def _db_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return f"sqlite:///{BASE_DIR / 'local.db'}"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = _db_url()


def load_content() -> dict:
    with open(BASE_DIR / "content" / "content.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONTENT = load_content()
