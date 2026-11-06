"""Tests for the admin user management endpoints (/api/admin/users)."""
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.models.user import UserRole
from app.security import verify_password
from tests.conftest import TEST_ADMIN_USERNAME
from tests.test_auth import create_user, login


def get_admin(db_session) -> User:
    return db_session.query(User).filter_by(username=TEST_ADMIN_USERNAME).first()


def test_list_users_requires_admin(db_session, client):
    create_user(db_session, username="bob")
    response = client.get("/api/admin/users")
    assert response.status_code == 200
    usernames = {u["username"] for u in response.json()}
    assert usernames == {TEST_ADMIN_USERNAME, "bob"}


def test_list_users_forbidden_for_regular_user(db_session, client):
    create_user(db_session)
    login(client)  # client is now bob (regular user)
    response = client.get("/api/admin/users")
    assert response.status_code == 403
    assert "Administratorrechte" in response.json()["detail"]


def test_create_user_as_admin(db_session, client):
    response = client.post(
        "/api/admin/users",
        json={"username": "newuser", "password": "a reasonably long password"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "newuser"
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert body["totp_enabled"] is False
    assert "password_hash" not in body


def test_create_user_rejects_duplicate_username(db_session, client):
    create_user(db_session, username="taken")
    response = client.post(
        "/api/admin/users",
        json={"username": "taken", "password": "a reasonably long password"},
    )
    assert response.status_code == 409


def test_create_user_rejects_weak_password(db_session, client):
    response = client.post(
        "/api/admin/users",
        json={"username": "weak", "password": "short"},
    )
    assert response.status_code == 400
    assert "15" in response.json()["detail"]


def test_create_user_requires_authentication(anon_client):
    response = anon_client.post(
        "/api/admin/users",
        json={"username": "intruder", "password": "a reasonably long password"},
    )
    assert response.status_code == 401


def test_update_role_and_deactivate(db_session, client):
    target = create_user(db_session, username="bob")
    response = client.patch(
        f"/api/admin/users/{target.id}",
        json={"is_active": False, "role": "admin"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin"
    assert body["is_active"] is False


def test_update_password_by_admin_invalidates_target_sessions(db_session, client):
    target = create_user(db_session, username="bob")
    # Bob logs in (creates a session)
    bob_client = TestClient(app)
    login(bob_client, username="bob")
    assert bob_client.get("/api/auth/me").status_code == 200

    response = client.patch(
        f"/api/admin/users/{target.id}",
        json={"new_password": "reset by admin long enough"},
    )
    assert response.status_code == 200
    # Bob's session must be invalidated
    assert bob_client.get("/api/auth/me").status_code == 401
    db_session.expire_all()
    refreshed = db_session.query(User).filter_by(username="bob").first()
    assert verify_password(refreshed.password_hash, "reset by admin long enough")


def test_admin_cannot_demote_themselves(db_session, client):
    admin = get_admin(db_session)
    response = client.patch(
        f"/api/admin/users/{admin.id}",
        json={"role": "user"},
    )
    assert response.status_code == 400
    assert "eigene Rolle" in response.json()["detail"]


def test_admin_cannot_deactivate_themselves(db_session, client):
    admin = get_admin(db_session)
    response = client.patch(
        f"/api/admin/users/{admin.id}",
        json={"is_active": False},
    )
    assert response.status_code == 400
    assert "Konto kann nicht deaktiviert" in response.json()["detail"]


def test_self_demote_takes_precedence_over_last_admin_check(db_session, client):
    # A second admin exists but is inactive -> the caller is the last
    # active admin. The self-demote check takes precedence (the
    # last-admin rule is unreachable through the API by another active
    # admin, so it is pure defense-in-depth).
    create_user(db_session, username="admin2", role=UserRole.ADMIN, is_active=False)
    admin = get_admin(db_session)
    response = client.patch(
        f"/api/admin/users/{admin.id}",
        json={"role": "user"},
    )
    assert response.status_code == 400
    assert "eigene Rolle" in response.json()["detail"]


def test_active_second_admin_can_be_demoted(db_session, client):
    second = create_user(db_session, username="admin2", role=UserRole.ADMIN)
    response = client.patch(
        f"/api/admin/users/{second.id}",
        json={"role": "user"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "user"


def test_update_unknown_user_returns_404(db_session, client):
    response = client.patch("/api/admin/users/9999", json={"is_active": False})
    assert response.status_code == 404


def test_reset_totp_clears_enrollment(db_session, client):
    secret_target = create_user(
        db_session, username="bob", totp_enabled=True, totp_secret="ABCDEF234567"
    )
    assert secret_target.totp_enabled is True
    response = client.patch(
        f"/api/admin/users/{secret_target.id}",
        json={"reset_totp": True},
    )
    assert response.status_code == 200
    assert response.json()["totp_enabled"] is False
    db_session.expire_all()
    refreshed = db_session.query(User).filter_by(username="bob").first()
    assert refreshed.totp_secret is None
    assert refreshed.totp_enabled is False
