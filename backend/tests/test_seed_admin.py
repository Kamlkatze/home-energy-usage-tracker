"""Tests for the seed_admin CLI (app.seed_admin)."""
import pytest

from app.models import User
from app.models.user import UserRole
from app.security import PasswordStrengthError, verify_password
from app.seed_admin import create_admin, main
from tests.test_auth import TEST_PASSWORD


def test_create_admin_creates_admin_role_user(db_session):
    user = create_admin(db_session, "root", TEST_PASSWORD)
    assert user.username == "root"
    assert user.role == UserRole.ADMIN
    assert user.is_active is True
    assert user.password_hash.startswith("$argon2")
    assert verify_password(user.password_hash, TEST_PASSWORD)


def test_create_admin_rejects_duplicate_username(db_session):
    create_admin(db_session, "root", TEST_PASSWORD)
    with pytest.raises(ValueError, match="existiert bereits"):
        create_admin(db_session, "root", TEST_PASSWORD)


def test_create_admin_rejects_weak_password(db_session):
    with pytest.raises(PasswordStrengthError):
        create_admin(db_session, "root", "short")


def test_cli_creates_admin_interactively(monkeypatch, db_session):
    import app.seed_admin as seed_mod

    monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db_session)
    monkeypatch.setattr("builtins.input", lambda prompt="": "cliadmin")
    monkeypatch.setattr(
        seed_mod.getpass, "getpass", lambda prompt="": TEST_PASSWORD
    )
    exit_code = main(argv=[])
    assert exit_code == 0
    user = db_session.query(User).filter_by(username="cliadmin").first()
    assert user is not None
    assert user.role == UserRole.ADMIN


def test_cli_rejects_existing_username(monkeypatch, db_session):
    import app.seed_admin as seed_mod

    create_admin(db_session, "cliadmin", TEST_PASSWORD)
    monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db_session)
    monkeypatch.setattr("builtins.input", lambda prompt="": "cliadmin")
    monkeypatch.setattr(
        seed_mod.getpass, "getpass", lambda prompt="": TEST_PASSWORD
    )
    assert main(argv=[]) == 1


def test_cli_rejects_empty_username(monkeypatch, db_session):
    import app.seed_admin as seed_mod

    monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db_session)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert main(argv=[]) == 1
