import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + _tmp.replace("\\", "/") + "/t.db"

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, main, whatsapp
from app.db import Member, RequestLog, SessionLocal, init_db
from app.services import delivery, otp

_real_send_template = whatsapp.send_template
init_db()
MSG = "your Membership No has been sent"


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    db = SessionLocal()
    db.query(RequestLog).delete()
    db.query(Member).delete()
    db.add(Member(member_id="KA12345", name="Asha Rao", email_norm="asha@example.com",
                  phone_e164="+919876543210"))
    db.commit()
    db.close()
    monkeypatch.setattr(config, "LOOKUP_MODE", "direct")
    monkeypatch.setattr(config, "INTERAKT_API_KEY", "")
    monkeypatch.setattr(config, "WA_TEMPLATE_MEMBER_ID", "")
    calls = {"email": [], "wa": []}
    monkeypatch.setattr(delivery, "send_member_id_email",
                        lambda *a: calls["email"].append(a) or True)
    monkeypatch.setattr(whatsapp, "send_template",
                        lambda *a: calls["wa"].append(a) or True)
    return calls


@pytest.fixture
def client():
    return TestClient(main.app)


def post(client, ident, ip="1.1.1.1"):
    return client.post("/lookup", data={"identifier": ident}, headers={"x-forwarded-for": ip})


def _member():
    db = SessionLocal()
    m = db.get(Member, "KA12345")
    db.close()
    return m


def test_identical_responses_no_id(client, setup):
    a = post(client, "asha@example.com")
    b = post(client, "9876543210")
    c = post(client, "nobody@x.com")
    for r in (a, b, c):
        assert r.status_code == 200 and MSG in r.text and "KA12345" not in r.text
    assert a.text == b.text == c.text
    assert len(setup["email"]) == 2
    assert setup["email"][0][2] == "KA12345"


def test_per_member_limit_same_message(client, setup):
    texts = [post(client, "asha@example.com", ip=f"2.2.2.{i}").text for i in range(5)]
    assert len(set(texts)) == 1 and MSG in texts[0]
    assert len(setup["email"]) == 3
    db = SessionLocal()
    outs = [r.outcome for r in db.query(RequestLog).filter_by(type="id_sent").order_by(RequestLog.id)]
    db.close()
    assert outs == ["email:sent,wa:disabled"] * 3 + ["rate_limited"] * 2


def test_ip_limit(client, setup):
    for _ in range(config.LOOKUPS_PER_IP_PER_HOUR):
        post(client, "nobody@x.com", ip="3.3.3.3")
    r = post(client, "asha@example.com", ip="3.3.3.3")
    assert "Too many attempts" in r.text and MSG not in r.text
    assert setup["email"] == []


def test_whatsapp_disabled_vs_enabled(client, setup, monkeypatch):
    post(client, "asha@example.com")
    assert setup["wa"] == [] and len(setup["email"]) == 1
    monkeypatch.setattr(config, "INTERAKT_API_KEY", "k")  # template still unset
    assert delivery.send_member_id(_member(), {})["whatsapp"] == "disabled"
    monkeypatch.setattr(config, "WA_TEMPLATE_MEMBER_ID", "tpl")
    assert delivery.send_member_id(_member(), {}) == {"email": "sent", "whatsapp": "sent"}
    assert setup["wa"][0] == ("+919876543210", "tpl", ["Asha Rao", "KA12345"])


def test_send_template_never_raises(monkeypatch):
    monkeypatch.setattr(config, "INTERAKT_API_KEY", "k")

    def boom(*a, **k):
        raise httpx.ConnectError("x")
    monkeypatch.setattr(httpx, "post", boom)
    assert _real_send_template("+919876543210", "t", ["a"]) is False


def test_otp_routes_404_in_direct_mode(client):
    assert client.post("/otp/request", data={"identifier": "a@b.com"}).status_code == 404
    assert client.post("/otp/verify", data={"identifier": "a@b.com", "code": "1"}).status_code == 404


def test_otp_mode_old_flow(client, monkeypatch):
    monkeypatch.setattr(config, "LOOKUP_MODE", "otp")
    sent = {}
    monkeypatch.setattr(otp, "send_otp_email", lambda to, name, code, ttl: sent.update(code=code) or True)
    assert client.post("/lookup", data={"identifier": "asha@example.com"}).status_code == 404
    r = client.post("/otp/request", data={"identifier": "asha@example.com"})
    assert r.status_code == 200 and "/otp/verify" in r.text
    r = client.post("/otp/verify", data={"identifier": "asha@example.com", "code": sent["code"]})
    assert "KA12345" in r.text
    assert 'hx-post="/otp/request"' in client.get("/").text


def test_direct_form_and_try_again(client):
    h = client.get("/").text
    assert 'hx-post="/lookup"' in h and "Send my Membership No" in h
    assert 'hx-get="/lookup-form"' in post(client, "x@y.com").text
    assert client.get("/lookup-form").status_code == 200
