"""Tests for the /api/auth endpoints (login, logout, me, change-password)."""
from datetime import UTC, datetime, timedelta

import pyotp
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.models.user import UserRole
from app.security import hash_password

TEST_PASSWORD = "correct horse battery staple"


def create_user(
    db_session,
    username: str = "alice",
    password: str = TEST_PASSWORD,
    role: UserRole = UserRole.USER,
    **kwargs,
) -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        **kwargs,
    )
    db_session.add(user)
    db_session.commit()
    return user


def login(client: TestClient, username: str = "alice", password: str = TEST_PASSWORD, **extra):
    return client.post("/api/auth/login", json={"username": username, "password": password, **extra})


def test_login_success_sets_http_only_cookie(db_session, client):
    create_user(db_session)
    response = login(client)
    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert response.json()["role"] == "user"
    assert response.json()["totp_enabled"] is False
    set_cookie = response.headers["set-cookie"]
    assert "et_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()
    assert "Secure" not in set_cookie  # COOKIE_SECURE defaults to false (LAN)


def test_login_success_me_returns_user(db_session, client):
    create_user(db_session)
    login(client)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert response.json()["role"] == "user"


def test_me_requires_authentication(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert "detail" in response.json()


def test_login_wrong_password_generic_error(db_session, client):
    create_user(db_session)
    response = login(client, password="wrong password entirely")
    assert response.status_code == 401
    assert response.json()["detail"] == "Ungültiger Benutzername oder Passwort."


def test_login_unknown_user_same_generic_error(db_session, client):
    create_user(db_session)
    known = login(client, password="wrong password entirely")
    unknown = login(client, username="does-not-exist", password="wrong password entirely")
    assert unknown.status_code == 401
    # Identical generic message for existing and non-existing users
    assert unknown.json()["detail"] == known.json()["detail"]


def test_logout_invalidates_session(db_session, client):
    create_user(db_session)
    login(client)
    assert client.get("/api/auth/me").status_code == 200
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_logout_without_session_is_idempotent(client):
    assert client.post("/api/auth/logout").status_code == 204


def test_account_lockout_after_first_failure(db_session, client):
    create_user(db_session)
    response = login(client, password="wrong password entirely")
    assert response.status_code == 401
    # Exponential lockout (OWASP): even the correct password is rejected
    # with 429 while the account is locked after a failed attempt
    response = login(client)
    assert response.status_code == 429
    assert "später" in response.json()["detail"]


def test_lockout_extends_and_caps_at_fifteen_minutes(db_session, client):
    create_user(db_session)
    login(client, password="wrong password entirely")
    db_session.expire_all()
    user = db_session.query(User).filter_by(username="alice").first()
    first_lock = user.locked_until
    assert first_lock is not None
    # Any further attempt extends the exponential lockout
    assert login(client, password="wrong password entirely").status_code == 429
    db_session.expire_all()
    user = db_session.query(User).filter_by(username="alice").first()
    assert user.locked_until > first_lock
    # Repeated attempts cap the lockout at 15 minutes (LOCKOUT_MAX_SECONDS)
    for _ in range(12):
        login(client, password="wrong password entirely")
    db_session.expire_all()
    user = db_session.query(User).filter_by(username="alice").first()
    remaining = user.locked_until - datetime.now(UTC)
    assert remaining <= timedelta(seconds=910)
    assert remaining > timedelta(seconds=600)


def test_successful_login_resets_lockout_counter(db_session, client):
    user = create_user(db_session)
    login(client, password="wrong password entirely")
    db_session.expire_all()
    assert db_session.query(User).filter_by(username="alice").first().failed_login_count == 1
    # Unlock manually (the 2-second initial lockout may have expired already)
    user.locked_until = None
    db_session.commit()
    assert login(client).status_code == 200
    db_session.expire_all()
    refreshed = db_session.query(User).filter_by(username="alice").first()
    assert refreshed.failed_login_count == 0
    assert refreshed.locked_until is None


def test_inactive_user_cannot_login(db_session, client):
    create_user(db_session, password=TEST_PASSWORD, is_active=False)
    response = login(client)
    assert response.status_code == 401
    assert response.json()["detail"] == "Ungültiger Benutzername oder Passwort."


def test_login_with_totp_enabled_requires_code(db_session, client):
    secret = pyotp.random_base32()
    create_user(db_session, totp_enabled=True, totp_secret=secret)
    response = login(client)
    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["totp_required"] is True
    assert "Zwei-Faktor-Code" in detail["message"]


def test_login_with_totp_invalid_code(db_session, client):
    secret = pyotp.random_base32()
    create_user(db_session, totp_enabled=True, totp_secret=secret)
    response = login(client, totp_code="000000")
    assert response.status_code == 401
    assert "Zwei-Faktor-Code" in response.json()["detail"]


def test_login_with_totp_valid_code(db_session, client):
    secret = pyotp.random_base32()
    create_user(db_session, totp_enabled=True, totp_secret=secret)
    code = pyotp.TOTP(secret).now()
    response = login(client, totp_code=code)
    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_change_password_requires_correct_current_password(db_session, client):
    create_user(db_session)
    login(client)
    response = client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong current", "new_password": "new longer password here"},
    )
    assert response.status_code == 401
    assert "Aktuelles Passwort" in response.json()["detail"]


def test_change_password_enforces_strength_policy(db_session, client):
    create_user(db_session)
    login(client)
    response = client.post(
        "/api/auth/change-password",
        json={"current_password": TEST_PASSWORD, "new_password": "short12"},
    )
    assert response.status_code == 400
    assert "15" in response.json()["detail"]


def test_change_password_success_and_relogin(db_session, client):
    create_user(db_session)
    login(client)
    new_password = "brand new longer password"
    response = client.post(
        "/api/auth/change-password",
        json={"current_password": TEST_PASSWORD, "new_password": new_password},
    )
    assert response.status_code == 200
    # Current session stays valid
    assert client.get("/api/auth/me").status_code == 200
    # Old password no longer works, new one does
    fresh_client = TestClient(app)
    assert login(fresh_client, password=TEST_PASSWORD).status_code == 401
    # The failed attempt above triggered the exponential lockout; clear it
    user = db_session.query(User).filter_by(username="alice").first()
    user.locked_until = None
    db_session.commit()
    assert login(fresh_client, password=new_password).status_code == 200


def test_change_password_logout_other_sessions(db_session, client):
    create_user(db_session)
    login(client)
    # A second, independent session (another browser)
    other_client = TestClient(app)
    login(other_client)
    assert other_client.get("/api/auth/me").status_code == 200

    new_password = "brand new longer password"
    response = client.post(
        "/api/auth/change-password",
        json={
            "current_password": TEST_PASSWORD,
            "new_password": new_password,
            "logout_other_sessions": True,
        },
    )
    assert response.status_code == 200
    # The current session survives, the other one is invalidated
    assert client.get("/api/auth/me").status_code == 200
    assert other_client.get("/api/auth/me").status_code == 401