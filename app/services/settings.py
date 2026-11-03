import json

from sqlalchemy.orm import Session

from ..config import CONTENT
from ..db import Setting

KEYS = ("voting_link", "process_bullets", "contact_number")


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(Setting, key)
    return row.value if row and row.value is not None else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


def public_settings(db: Session) -> dict:
    """Admin-editable values merged over content.yaml defaults."""
    c = CONTENT
    bullets_raw = get_setting(db, "process_bullets", "")
    bullets = [b.strip() for b in bullets_raw.splitlines() if b.strip()] or c["voting"]["default_process"]
    return {
        "voting_link": get_setting(db, "voting_link", c["voting"]["default_link"]).strip(),
        "process_bullets": bullets,
        "contact_number": get_setting(db, "contact_number", c["contact"]["phone"]).strip(),
        "voting_dates": c["voting"]["dates"],
    }
