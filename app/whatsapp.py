import logging
import re

import httpx

from . import config

log = logging.getLogger("whatsapp")

API_URL = "https://api.interakt.ai/v1/public/message/"


def enabled() -> bool:
    """WhatsApp is active only when both env vars are set."""
    return bool(config.INTERAKT_API_KEY and config.WA_TEMPLATE_MEMBER_ID)


def send_template(phone_e164: str, template_name: str, body_values: list[str]) -> bool:
    """Send an Interakt template message. Never raises."""
    try:
        if not config.INTERAKT_API_KEY:
            log.error("INTERAKT_API_KEY missing")
            return False
        digits = re.sub(r"\D", "", phone_e164 or "")[-10:]
        if len(digits) != 10:
            log.error("Invalid phone for WhatsApp")
            return False
        r = httpx.post(
            API_URL,
            headers={"Authorization": f"Basic {config.INTERAKT_API_KEY}",
                     "Content-Type": "application/json"},
            json={"countryCode": "+91", "phoneNumber": digits, "type": "Template",
                  "template": {"name": template_name, "languageCode": "en",
                               "bodyValues": [str(v) for v in body_values]}},
            timeout=10,
        )
        if r.status_code >= 300:
            log.error("Interakt error %s: %s", r.status_code, r.text[:300])
            return False
        return True
    except Exception as e:  # never raise
        log.error("Interakt request failed: %s", e)
        return False
