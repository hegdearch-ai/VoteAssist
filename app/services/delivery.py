import logging

from .. import config, whatsapp
from ..db import Member
from ..mailer import send_member_id_email

log = logging.getLogger("delivery")


def send_member_id(member: Member, s: dict) -> dict:
    """Send the Membership No by email and (if enabled) WhatsApp. `s` = public_settings().
    Returns {"email": sent|failed|no_email, "whatsapp": sent|failed|disabled|no_phone}."""
    result = {"email": "no_email", "whatsapp": "disabled"}

    if member.email_norm:
        try:
            ok = send_member_id_email(member.email_norm, member.name, member.member_id,
                                      s.get("voting_dates", ""), s.get("voting_link", ""))
        except Exception as e:
            log.error("Email delivery failed: %s", e)
            ok = False
        result["email"] = "sent" if ok else "failed"

    if whatsapp.enabled():
        if not member.phone_e164:
            result["whatsapp"] = "no_phone"
        else:
            ok = whatsapp.send_template(member.phone_e164, config.WA_TEMPLATE_MEMBER_ID,
                                        [member.name, member.member_id])
            result["whatsapp"] = "sent" if ok else "failed"
    return result
