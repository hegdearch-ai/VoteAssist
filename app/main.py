import csv
import importlib
import io
import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from . import config
from .config import (ADMIN_PASSWORD, BASE_DIR, CONTENT, ENABLED_ADDONS,
                     ID_SENDS_PER_MEMBER_PER_HOUR, LOOKUPS_PER_IP_PER_HOUR, OTP_TTL_MIN)
from .db import Member, RequestLog, SessionLocal, get_db, init_db
from .services.delivery import send_member_id
from .services.logging import count_recent, count_recent_member, hash_ip, log_request
from .services.members import find_member, mask_identifier
from .services.otp import issue_otp, verify_otp
from .services.settings import KEYS, get_setting, public_settings, set_setting

log = logging.getLogger("app")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="VoteAssist", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

# ---- Add-on hook -----------------------------------------------------------
# Each add-on is a module app/addons/<name>.py exposing `router` (FastAPI APIRouter)
# and optionally `widget_template` (path of a Jinja partial shown on the landing page).
ADDON_WIDGETS: list[str] = []
for _name in ENABLED_ADDONS:
    try:
        _mod = importlib.import_module(f"app.addons.{_name}")
        app.include_router(_mod.router)
        if getattr(_mod, "widget_template", None):
            ADDON_WIDGETS.append(_mod.widget_template)
        log.info("Add-on enabled: %s", _name)
    except Exception as e:  # never let an add-on take the site down
        log.error("Add-on %s failed to load: %s", _name, e)


# ---- Helpers ---------------------------------------------------------------
def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    return xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")


def render(request: Request, name: str, **ctx):
    return templates.TemplateResponse(
        request, name, {"c": CONTENT, "lookup_mode": config.LOOKUP_MODE, **ctx})


GENERIC_SENT = ("If this matches a registered member, a 6-digit code has been sent to the "
                "email address on file. It is valid for %d minutes." % OTP_TTL_MIN)


# ---- Public routes ---------------------------------------------------------
@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    return PlainTextResponse("ok")


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    return render(request, "index.html", s=public_settings(db), addon_widgets=ADDON_WIDGETS)


GENERIC_ID_SENT = ("If you are a registered member, your Membership No has been sent to your "
                   "registered email and WhatsApp number. Please check your inbox (and spam folder).")


@app.get("/lookup-form", response_class=HTMLResponse)
def lookup_form(request: Request, db: Session = Depends(get_db)):
    return render(request, "partials/lookup_form.html", s=public_settings(db))


@app.post("/lookup", response_class=HTMLResponse)
def lookup(request: Request, identifier: str = Form(..., max_length=120),
           db: Session = Depends(get_db)):
    if config.LOOKUP_MODE != "direct":
        raise HTTPException(404)
    ip = hash_ip(client_ip(request))
    masked = mask_identifier(identifier)
    s = public_settings(db)

    if count_recent(db, type="lookup", ip_hash=ip) >= LOOKUPS_PER_IP_PER_HOUR:
        log_request(db, type="lookup", outcome="ip_limited", identifier_masked=masked, ip_hash=ip)
        return render(request, "partials/lookup_form.html",
                      error="Too many attempts. Please try again after some time or call us.",
                      s=s, identifier=identifier)

    member = find_member(db, identifier)
    log_request(db, type="lookup", outcome="matched" if member else "not_found",
                member_id=member.member_id if member else None, identifier_masked=masked, ip_hash=ip)

    if member:
        if count_recent_member(db, type="id_sent", member_id=member.member_id,
                               exclude_outcome="rate_limited") >= ID_SENDS_PER_MEMBER_PER_HOUR:
            log_request(db, type="id_sent", outcome="rate_limited", member_id=member.member_id,
                        identifier_masked=masked, ip_hash=ip)
        else:
            res = send_member_id(member, s)
            log_request(db, type="id_sent", member_id=member.member_id, identifier_masked=masked,
                        outcome=f"email:{res['email']},wa:{res['whatsapp']}", ip_hash=ip)

    # Identical response whether or not a member was found / limited (no enumeration)
    resp = render(request, "partials/sent.html", notice=GENERIC_ID_SENT, s=s)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.post("/otp/request", response_class=HTMLResponse)
def otp_request(request: Request, identifier: str = Form(..., max_length=120),
                db: Session = Depends(get_db)):
    if config.LOOKUP_MODE != "otp":
        raise HTTPException(404)
    ip = hash_ip(client_ip(request))
    masked = mask_identifier(identifier)

    if count_recent(db, type="lookup", ip_hash=ip) >= LOOKUPS_PER_IP_PER_HOUR:
        log_request(db, type="lookup", outcome="ip_limited", identifier_masked=masked, ip_hash=ip)
        return render(request, "partials/lookup_form.html",
                      error="Too many attempts. Please try again after some time or call us.",
                      s=public_settings(db), identifier=identifier)

    member = find_member(db, identifier)
    log_request(db, type="lookup", outcome="matched" if member else "not_found",
                member_id=member.member_id if member else None, identifier_masked=masked, ip_hash=ip)

    if member:
        outcome = issue_otp(db, member)
        log_request(db, type="otp_sent", outcome=outcome, member_id=member.member_id,
                    identifier_masked=masked, ip_hash=ip)
        if outcome == "rate_limited":
            return render(request, "partials/lookup_form.html",
                          error="Too many codes requested. Please try again after an hour or call us.",
                          s=public_settings(db), identifier=identifier)

    # Same response whether or not a member was found (no enumeration)
    return render(request, "partials/otp_form.html", identifier=identifier, notice=GENERIC_SENT,
                  s=public_settings(db))


@app.post("/otp/verify", response_class=HTMLResponse)
def otp_verify(request: Request, identifier: str = Form(..., max_length=120),
               code: str = Form(..., max_length=10), db: Session = Depends(get_db)):
    if config.LOOKUP_MODE != "otp":
        raise HTTPException(404)
    ip = hash_ip(client_ip(request))
    masked = mask_identifier(identifier)
    member = find_member(db, identifier)
    outcome = verify_otp(db, member, code) if member else "invalid"
    log_request(db, type="otp_verified" if outcome == "success" else "otp_failed", outcome=outcome,
                member_id=member.member_id if member else None, identifier_masked=masked, ip_hash=ip)

    if outcome == "success":
        resp = render(request, "partials/result.html", member=member, s=public_settings(db))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    msgs = {
        "expired": "This code has expired. Please request a new one.",
        "locked": "Too many wrong attempts. Please request a new code.",
        "invalid": "That code is not correct. Please check and try again.",
    }
    if outcome in ("expired", "locked"):
        return render(request, "partials/lookup_form.html", error=msgs[outcome],
                      s=public_settings(db), identifier=identifier)
    return render(request, "partials/otp_form.html", identifier=identifier, error=msgs[outcome],
                  s=public_settings(db))


# ---- Admin -----------------------------------------------------------------
_basic = HTTPBasic()


def admin_auth(creds: HTTPBasicCredentials = Depends(_basic)):
    if not ADMIN_PASSWORD or not secrets.compare_digest(creds.password.encode(), ADMIN_PASSWORD.encode()):
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})


@app.get("/admin", response_class=HTMLResponse, dependencies=[Depends(admin_auth)])
def admin_page(request: Request, saved: int = 0, db: Session = Depends(get_db)):
    s = public_settings(db)
    members = db.scalar(select(func.count()).select_from(Member)) or 0
    logs = db.scalar(select(func.count()).select_from(RequestLog)) or 0
    return render(request, "admin.html", s=s, bullets_text="\n".join(s["process_bullets"]),
                  saved=bool(saved), members=members, logs=logs)


@app.post("/admin", dependencies=[Depends(admin_auth)])
def admin_save(voting_link: str = Form(""), process_bullets: str = Form(""),
               contact_number: str = Form(""), db: Session = Depends(get_db)):
    set_setting(db, "voting_link", voting_link.strip())
    set_setting(db, "process_bullets", process_bullets.strip())
    set_setting(db, "contact_number", contact_number.strip())
    return Response(status_code=303, headers={"Location": "/admin?saved=1"})


@app.get("/admin/log.csv", dependencies=[Depends(admin_auth)])
def admin_log_csv(db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = ["id", "ts", "channel", "type", "member_id", "identifier_masked", "question_text",
            "outcome", "ip_hash"]
    w.writerow(cols)
    for r in db.scalars(select(RequestLog).order_by(RequestLog.id)):
        w.writerow([getattr(r, c) for c in cols])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=request_log.csv"})
