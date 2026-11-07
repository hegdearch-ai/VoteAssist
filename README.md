# VoteAssist

Campaign page + Membership No lookup (one-click send by email/WhatsApp; email-OTP mode kept) for Dr. Madhav Hegde, IRIA Karnataka 2026.
FastAPI · Jinja2 + HTMX · Postgres · Resend. Chatbot and WhatsApp are opt-in add-ons (`app/addons/README.md`).

## Run locally
    pip install -r requirements.txt
    uvicorn app.main:app --reload
Without `EMAIL_API_KEY` (and `APP_ENV` != production) the OTP is printed to the console. SQLite is used when `DATABASE_URL` is empty.

## Import members (once, from a laptop; never commit the Excel)
    railway run python scripts/import_members.py members.xlsx
Columns: Sr No, Member Name, Membership No, Email ID, Mobile No, City. Re-running upserts.

## Deploy (Railway)
Add Postgres, reference `DATABASE_URL`, set `OTP_SECRET`, `ADMIN_PASSWORD`, `EMAIL_API_KEY`, `EMAIL_FROM`, `EMAIL_REPLY_TO`, `APP_ENV=production`. Custom domain: `vote.ibrag.co.in`.

## Lookup modes
`LOOKUP_MODE` env var:
- `direct`: `POST /lookup` sends the Membership No to the member's email (and WhatsApp if enabled). The page always shows the same generic message and never the number. `/otp/*` return 404.
- `otp`: the original email-OTP flow (`/otp/request`, `/otp/verify`); `/lookup` returns 404.
- `show` (default): `POST /lookup` shows the Membership No on the page with no verification. If the email isn't found it asks for the mobile number (and vice versa); if both fail it shows the contact number to call. Note: this reveals whether an email/mobile is registered. `/otp/*` return 404.

Switch by setting `LOOKUP_MODE` and restarting. Limits: 10 lookups per IP per hour, 3 sends per member per hour.

## Enable WhatsApp (Interakt)
Set both `INTERAKT_API_KEY` and `WA_TEMPLATE_MEMBER_ID` (the name of an approved Interakt template, language `en`, with two body variables: member name, then Membership No). Until both are set WhatsApp is "disabled" and only the email is sent. Numbers go out as +91 plus 10 digits.

## Admin
`/admin` (any username, password = `ADMIN_PASSWORD`): voting link, process bullets, contact number, CSV request log.
