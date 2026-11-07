import hashlib
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import OTP_SECRET
from ..db import RequestLog, utcnow


def hash_ip(ip: str) -> str:
    return hashlib.sha256(f"{ip}:{OTP_SECRET}".encode()).hexdigest()[:32]


def log_request(db: Session, *, type: str, outcome: str | None = None, channel: str = "web",
                member_id: str | None = None, identifier_masked: str | None = None,
                question_text: str | None = None, ip_hash: str | None = None) -> None:
    db.add(RequestLog(type=type, outcome=outcome, channel=channel, member_id=member_id,
                      identifier_masked=identifier_masked,
                      question_text=(question_text or None) and question_text[:500],
                      ip_hash=ip_hash))
    db.commit()


def count_recent(db: Session, *, type: str, ip_hash: str, minutes: int = 60) -> int:
    since = utcnow() - timedelta(minutes=minutes)
    return db.scalar(select(func.count()).select_from(RequestLog).where(
        RequestLog.type == type, RequestLog.ip_hash == ip_hash, RequestLog.ts >= since)) or 0


def count_recent_member(db: Session, *, type: str, member_id: str, minutes: int = 60,
                        exclude_outcome: str | None = None) -> int:
    since = utcnow() - timedelta(minutes=minutes)
    q = select(func.count()).select_from(RequestLog).where(
        RequestLog.type == type, RequestLog.member_id == member_id, RequestLog.ts >= since)
    if exclude_outcome:
        q = q.where(RequestLog.outcome != exclude_outcome)
    return db.scalar(q) or 0
