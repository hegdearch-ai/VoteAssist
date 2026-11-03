# VoteAssist

Campaign page + Membership No lookup (email OTP) for Dr. Madhav Hegde, IRIA Karnataka 2026.
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

## Admin
`/admin` (any username, password = `ADMIN_PASSWORD`): voting link, process bullets, contact number, CSV request log.
