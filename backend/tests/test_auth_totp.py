"""Tests for the TOTP enrollment endpoints (/api/auth/totp)."""
import pyotp
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from tests.test_auth import TEST_PASSWORD, create_user, login


def totp_headers_code(secret: str) -> str:
    return pyotp.TOTP(secret).now()


def test_totp_status_defaults(db_session, client):
    create_user(db_session)
    login(client)
    response = client.get("/api/auth/totp")
    assert response.status_code == 200
    assert response.json() == {"enabled": False, "pending_setup": False}


def test_totp_requires_authentication(anon_client):
    assert anon_client.get("/api/auth/totp").status_code == 401
    assert anon_client.post("/api/auth/totp/setup").status_code == 401


def test_totp_setup_returns_secret_and_otpauth_url(db_session, client):
    create_user(db_session)
    login(client)
    response = client.post("/api/auth/totp/setup")
    assert response.status_code == 200
    body = response.json()
    assert len(body["secret"]) >= 16
    assert "otpauth://totp/" in body["otpauth_url"]
    assert "Energy%20Tracker" in body["otpauth_url"]
    assert "alice" in body["otpauth_url"]
    # Secret is stored but TOTP stays disabled until confirmation
    db_session.expire_all()
    user = db_session.query(User).filter_by(username="alice").first()
    assert user.totp_secret is not None
    assert user.totp_enabled is False


def test_totp_setup_replaces_pending_secret(db_session, client):
    create_user(db_session)
    login(client)
    first = client.post("/api/auth/totp/setup").json()
    second = client.post("/api/auth/totp/setup").json()
    assert first["secret"] != second["secret"]
    db_session.expire_all()
    user = db_session.query(User).filter_by(username="alice").first()
    assert user.totp_secret == second["secret"]


def test_totp_setup_rejected_when_already_enabled(db_session, client):
    secret = pyotp.random_base32()
    create_user(db_session, totp_enabled=True, totp_secret=secret)
    login(client, totp_code=totp_headers_code(secret))
    response = client.post("/api/auth/totp/setup")
    assert response.status_code == 400
    assert "bereits aktiviert" in response.json()["detail"]


def test_totp_enable_without_setup_rejected(db_session, client):
    create_user(db_session)
    login(client)
    response = client.post("/api/auth/totp/enable", json={"code": "123456"})
    assert response.status_code == 400
    assert "nicht gestartet" in response.json()["detail"]


def test_totp_enable_with_wrong_code_rejected(db_session, client):
    create_user(db_session)
    login(client)
    client.post("/api/auth/totp/setup")
    response = client.post("/api/auth/totp/enable", json={"code": "000000"})
    assert response.status_code == 400
    assert "Ungültiger Zwei-Faktor-Code" in response.json()["detail"]
    db_session.expire_all()
    user = db_session.query(User).filter_by(username="alice").first()
    assert user.totp_enabled is False


def test_totp_enable_with_valid_code_activates(db_session, client):
    create_user(db_session)
    login(client)
    secret = client.post("/api/auth/totp/setup").json()["secret"]
    response = client.post("/api/auth/totp/enable", json={"code": totp_headers_code(secret)})
    assert response.status_code == 200
    assert response.json() == {"enabled": True, "pending_setup": False}
    db_session.expire_all()
    user = db_session.query(User).filter_by(username="alice").first()
    assert user.totp_enabled is True


def test_totp_enable_reports_pending_setup_before_confirmation(db_session, client):
    create_user(db_session)
    login(client)
    client.post("/api/auth/totp/setup")
    response = client.get("/api/auth/totp")
    assert response.status_code == 200
    assert response.json() == {"enabled": False, "pending_setup": True}


def test_totp_full_flow_login_after_enable(db_session, client):
    create_user(db_session)
    login(client)
    secret = client.post("/api/auth/totp/setup").json()["secret"]
    assert client.post("/api/auth/totp/enable", json={"code": totp_headers_code(secret)}).status_code == 200
    # Fresh session: login now requires the TOTP code
    fresh_client = TestClient(app)
    response = login(fresh_client)
    assert response.status_code == 401
    assert response.json()["detail"]["totp_required"] is True
    # The failed attempt locked the account (exponential lockout); clear it
    user = db_session.query(User).filter_by(username="alice").first()
    user.locked_until = None
    db_session.commit()
    code = totp_headers_code(secret)
    assert login(fresh_client, totp_code=code).status_code == 200
    assert fresh_client.get("/api/auth/me").json()["totp_enabled"] is True


def test_totp_disable_requires_current_password(db_session, client):
    secret = pyotp.random_base32()
    create_user(db_session, totp_enabled=True, totp_secret=secret)
    login(client, totp_code=totp_headers_code(secret))
    response = client.post(
        "/api/auth/totp/disable",
        json={"password": "wrong current password", "code": totp_headers_code(secret)},
    )
    assert response.status_code == 401
    assert "Aktuelles Passwort" in response.json()["detail"]


def test_totp_disable_requires_valid_code(db_session, client):
    secret = pyotp.random_base32()
    create_user(db_session, totp_enabled=True, totp_secret=secret)
    login(client, totp_code=totp_headers_code(secret))
    response = client.post(
        "/api/auth/totp/disable",
        json={"password": TEST_PASSWORD, "code": "000000"},
    )
    assert response.status_code == 400
    db_session.expire_all()
    user = db_session.query(User).filter_by(username="alice").first()
    assert user.totp_enabled is True


def test_totp_disable_deactivates_and_clears_secret(db_session, client):
    secret = pyotp.random_base32()
    create_user(db_session, totp_enabled=True, totp_secret=secret)
    login(client, totp_code=totp_headers_code(secret))
    response = client.post(
        "/api/auth/totp/disable",
        json={"password": TEST_PASSWORD, "code": totp_headers_code(secret)},
    )
    assert response.status_code == 200
    assert response.json() == {"enabled": False, "pending_setup": False}
    db_session.expire_all()
    user = db_session.query(User).filter_by(username="alice").first()
    assert user.totp_secret is None
    assert user.totp_enabled is False
    # Login without TOTP code works again
    fresh_client = TestClient(app)
    assert login(fresh_client).status_code == 200


def test_totp_disable_when_not_enabled_rejected(db_session, client):
    create_user(db_session)
    login(client)
    response = client.post(
        "/api/auth/totp/disable",
        json={"password": TEST_PASSWORD, "code": "123456"},
    )
    assert response.status_code == 400
    assert "nicht aktiviert" in response.json()["detail"]