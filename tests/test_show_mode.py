import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.db import RequestLog
from app.services.settings import set_setting
from tests.test_lookup import SessionLocal, setup  # noqa: F401  (shared DB + autouse fixture)

TRY_MOBILE = "Please try your registered mobile number instead"
TRY_EMAIL = "Please try your registered email instead"
CONTACT = "couldn't find your Membership No with either"


@pytest.fixture(autouse=True)
def show_mode(setup, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "LOOKUP_MODE", "show")


@pytest.fixture
def client():
    return TestClient(main.app)


def post(client, ident, tried="", ip="9.9.9.9"):
    data = {"identifier": ident}
    if tried:
        data["tried"] = tried
    return client.post("/lookup", data=data, headers={"x-forwarded-for": ip})


def test_found_by_email_shows_id(client, setup):  # noqa: F811
    r = post(client, "asha@example.com")
    assert "KA12345" in r.text and "Asha Rao" in r.text and "Verified" not in r.text
    assert r.headers["cache-control"] == "no-store"
    assert setup["email"] == [] and setup["wa"] == []


def test_result_has_copy_button_and_steps(client):
    r = post(client, "asha@example.com")
    assert 'data-copy="KA12345"' in r.text and "Copy Membership No" in r.text
    assert "How to vote" in r.text and "paste it in and cast your vote" in r.text
    assert "once the link is shared" in r.text  # no voting link configured


def test_steps_point_to_voting_link_when_set(client):
    db = SessionLocal()
    set_setting(db, "voting_link", "https://vote.example.org")
    db.close()
    r = post(client, "asha@example.com")
    assert "Open the voting page using the button below" in r.text
    assert 'href="https://vote.example.org"' in r.text


def test_copy_script_served(client):
    assert 'src="/static/copy.js"' in client.get("/").text
    assert "data-copy" in client.get("/static/copy.js").text


def test_found_by_phone_shows_id(client):
    assert "KA12345" in post(client, "+91 98765 43210").text


def test_email_fails_then_phone_fails_suggests_call(client):
    r = post(client, "nobody@x.com")
    assert TRY_MOBILE in r.text and 'name="tried" value="email"' in r.text
    r = post(client, "9000000000", tried="email")
    assert CONTACT in r.text and 'href="tel:' in r.text


def test_phone_fails_then_email_fails_suggests_call(client):
    r = post(client, "9000000000")
    assert TRY_EMAIL in r.text and 'value="phone"' in r.text
    assert CONTACT in post(client, "nobody@x.com", tried="phone").text


def test_email_fails_then_phone_succeeds(client):
    post(client, "nobody@x.com")
    assert "KA12345" in post(client, "9876543210", tried="email").text


def test_same_kind_twice_still_prompts_other(client):
    assert TRY_MOBILE in post(client, "other@x.com", tried="email").text


def test_invalid_input(client):
    r = post(client, "hello")
    assert "valid email or 10-digit mobile" in r.text
    db = SessionLocal()
    assert db.query(RequestLog).count() == 0
    db.close()


def test_ip_limit(client):
    for _ in range(config.LOOKUPS_PER_IP_PER_HOUR):
        post(client, "nobody@x.com", ip="8.8.8.8")
    r = post(client, "asha@example.com", ip="8.8.8.8")
    assert "Too many attempts" in r.text and "KA12345" not in r.text


def test_page_and_otp_routes(client):
    h = client.get("/").text
    assert 'hx-post="/lookup"' in h and "Show my Membership No" in h and "to see your Membership No" in h
    assert client.post("/otp/request", data={"identifier": "a@b.com"}).status_code == 404


def test_direct_mode_unchanged_no_hint(client, monkeypatch):
    monkeypatch.setattr(config, "LOOKUP_MODE", "direct")
    r = post(client, "nobody@x.com")
    assert TRY_MOBILE not in r.text and "has been sent" in r.text
