"""CLI to create an administrator user (e.g. the first admin after setup).

Usage:
    python -m app.seed_admin
    python -m app.seed_admin --username admin --password "..."
    /opt/venv/bin/python -m app.seed_admin   (inside the prod container)

Interactive mode prompts for username and password (getpass, no echo).
"""

import argparse
import getpass
import sys

from .database import SessionLocal
from .models import User
from .models.user import UserRole
from .security import PasswordStrengthError, hash_password, validate_password_strength


def create_admin(db, username: str, password: str) -> User:
    """Create an admin user; raises ValueError on duplicate username or
    a password that violates the strength policy."""
    if db.query(User).filter(User.username == username).first() is not None:
        raise ValueError(f"Benutzer '{username}' existiert bereits.")
    validate_password_strength(password, mfa_enabled=False)
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Erstellt einen Administrator-Benutzer für den Energy Tracker."
    )
    parser.add_argument("--username", help="Benutzername (sonst interaktiv abgefragt)")
    parser.add_argument(
        "--password",
        help="Passwort (sonst interaktiv abgefragt)",
    )
    args = parser.parse_args(argv)

    username = (args.username or input("Benutzername: ")).strip()
    if not username:
        print("Fehler: Benutzername darf nicht leer sein.", file=sys.stderr)
        return 1
    password = args.password or getpass.getpass("Passwort: ")
    if not password:
        print("Fehler: Passwort darf nicht leer sein.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        user = create_admin(db, username, password)
        print(f"Administrator '{user.username}' wurde angelegt.")
        return 0
    except PasswordStrengthError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())