import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import (OTP_MAX_ATTEMPTS, OTP_PER_MEMBER_PER_HOUR, OTP_SECRET, OTP_TTL_MIN)
from ..db import Member, OtpRequest, utcnow
from ..mailer import send_otp_email


def _hash(member_id: str, code: str) -> str:
    return hmac.new(OTP_SECRET.encode(), f"{member_id}:{code}".encode(), hashlib.sha256).hexdigest()


def issue_otp(db: Session, member: Member) -> str:
    """Returns outcome: sent | rate_limited | no_email | send_failed."""
    if not member.email_norm:
        return "no_email"
    since = utcnow() - timedelta(hours=1)
    recent = db.scalar(select(func.count()).select_from(OtpRequest).where(
        OtpRequest.member_id == member.member_id, OtpRequest.created_at >= since)) or 0
    if recent >= OTP_PER_MEMBER_PER_HOUR:
        return "rate_limited"
    code = f"{secrets.randbelow(10**6):06d}"
    # invalidate older codes
    for old in db.scalars(select(OtpRequest).where(
            OtpRequest.member_id == member.member_id, OtpRequest.used == False)):  # noqa: E712
        old.used = True
    db.add(OtpRequest(member_id=member.member_id, code_hash=_hash(member.member_id, code),
                      expires_at=utcnow() + timedelta(minutes=OTP_TTL_MIN)))
    db.commit()
    ok = send_otp_email(member.email_norm, member.name, code, OTP_TTL_MIN)
    return "sent" if ok else "send_failed"


def verify_otp(db: Session, member: Member, code: str) -> str:
    """Returns outcome: success | invalid | expired | locked."""
    otp = db.scalars(select(OtpRequest).where(
        OtpRequest.member_id == member.member_id, OtpRequest.used == False)  # noqa: E712
        .order_by(OtpRequest.id.desc())).first()
    if not otp or otp.expires_at < utcnow():
        return "expired"
    if otp.attempts >= OTP_MAX_ATTEMPTS:
        return "locked"
    otp.attempts += 1
    if hmac.compare_digest(otp.code_hash, _hash(member.member_id, (code or "").strip())):
        otp.used = True
        db.commit()
        return "success"
    db.commit()
    return "locked" if otp.attempts >= OTP_MAX_ATTEMPTS else "invalid"
