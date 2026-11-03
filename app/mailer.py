import logging

import httpx

from .config import APP_ENV, EMAIL_API_KEY, EMAIL_FROM, EMAIL_REPLY_TO

log = logging.getLogger("mailer")


def send_email(to: str, subject: str, html: str, text: str) -> bool:
    """Send via Resend HTTP API. Returns True on success."""
    if not EMAIL_API_KEY:
        if APP_ENV != "production":
            log.warning("DEV MODE (no EMAIL_API_KEY) to=%s subject=%s body=%s", to, subject, text)
            return True
        log.error("EMAIL_API_KEY missing in production")
        return False
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {EMAIL_API_KEY}"},
            json={"from": EMAIL_FROM, "to": [to], "reply_to": EMAIL_REPLY_TO,
                  "subject": subject, "html": html, "text": text},
            timeout=10,
        )
        if r.status_code >= 300:
            log.error("Resend error %s: %s", r.status_code, r.text[:300])
            return False
        return True
    except httpx.HTTPError as e:
        log.error("Resend request failed: %s", e)
        return False


def send_otp_email(to: str, name: str, code: str, ttl_min: int) -> bool:
    text = (f"Dear {name},\n\nYour verification code is {code}. It is valid for {ttl_min} minutes.\n"
            "If you did not request this, please ignore this email.\n\n"
            "This is an automated message; replies go to the campaign contact.")
    html = f"""<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;color:#222">
<p>Dear {name},</p>
<p>Your verification code to view your IRIA Membership No is:</p>
<p style="font-size:32px;letter-spacing:8px;font-weight:700;color:#2f5e22;margin:16px 0">{code}</p>
<p>Valid for {ttl_min} minutes. If you did not request this, please ignore this email.</p>
<p style="color:#777;font-size:12px">Campaign page of Dr. Madhav Hegde, IRIA Karnataka President-Elect candidate.</p></div>"""
    return send_email(to, f"Your verification code: {code}", html, text)
