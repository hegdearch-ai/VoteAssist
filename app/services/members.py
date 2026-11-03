import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Member

_PHONE_RE = re.compile(r"(?:\+?91)?([6-9]\d{9})")


def norm_email(value: str | None) -> str | None:
    value = (value or "").strip().lower()
    return value if "@" in value else None


def norm_phone(value) -> str | None:
    """Return +91XXXXXXXXXX or None. Accepts floats/ints from Excel."""
    if value is None:
        return None
    if isinstance(value, float):
        value = int(value)
    digits = re.sub(r"[\s\-().]", "", str(value))
    m = _PHONE_RE.search(digits)
    return f"+91{m.group(1)}" if m else None


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}"


def mask_phone(phone: str | None) -> str | None:
    return f"{phone[:3]}*****{phone[-3:]}" if phone and len(phone) >= 8 else None


def mask_identifier(raw: str) -> str:
    e = norm_email(raw)
    if e:
        return mask_email(e) or "?"
    p = norm_phone(raw)
    return mask_phone(p) or "invalid"


def find_member(db: Session, raw: str) -> Member | None:
    """Look up by registered email or mobile. Returns None if no match or ambiguous input."""
    raw = (raw or "").strip()
    if not raw:
        return None
    email = norm_email(raw)
    if email:
        return db.scalars(select(Member).where(Member.email_norm == email)).first()
    phone = norm_phone(raw)
    if phone:
        return db.scalars(select(Member).where(Member.phone_e164 == phone)).first()
    return None
