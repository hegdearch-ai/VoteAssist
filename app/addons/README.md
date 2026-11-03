# Add-ons (plug-in slots)

Nothing here is loaded unless named in `ENABLED_ADDONS` (comma-separated env var).

An add-on is one module `app/addons/<name>.py` that exposes:

```python
from fastapi import APIRouter
router = APIRouter()                       # required: your routes
widget_template = "addons/<name>_widget.html"   # optional: partial shown on the landing page
```

Reuse the shared services so every channel behaves identically:

| Need | Import |
|---|---|
| Find member by email/phone | `app.services.members.find_member` |
| Send/verify OTP | `app.services.otp.issue_otp / verify_otp` |
| Log every request (channel="chat"/"whatsapp") | `app.services.logging.log_request` |
| Admin-editable values (contact number, voting link) | `app.services.settings.public_settings` |

Planned:
- `chatbot.py`: Claude Haiku, answers only from `docs/` official documents, falls back to the contact number. Needs `ANTHROPIC_API_KEY`.
- `whatsapp.py`: Interakt webhook `POST /whatsapp/webhook` + `wa_sessions` table (already created). Needs `INTERAKT_API_KEY`.
