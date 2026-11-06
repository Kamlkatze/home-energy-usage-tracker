from collections.abc import Generator
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import AuthSession, User
from ..models.user import UserRole
from ..security import hash_session_token


def get_database_session(
    db: Session = Depends(get_db)
) -> Generator[Session]:
    yield db


def get_authenticated(
    request: Request,
    db: Session = Depends(get_db),
) -> tuple[User, AuthSession]:
    """Validate the session cookie and return (user, auth_session).

    Raises 401 if the cookie is missing, the session is unknown or
    expired, or the user has been deactivated.
    """
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nicht authentifiziert. Bitte melden Sie sich an.",
        )
    auth_session = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == hash_session_token(token))
        .first()
    )
    if auth_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nicht authentifiziert. Bitte melden Sie sich an.",
        )
    if auth_session.expires_at < datetime.now(UTC):
        db.delete(auth_session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sitzung abgelaufen. Bitte melden Sie sich erneut an.",
        )
    user = auth_session.user
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nicht authentifiziert. Bitte melden Sie sich an.",
        )
    auth_session.last_used_at = datetime.now(UTC)
    db.commit()
    return user, auth_session


def get_current_user(user: tuple[User, AuthSession] = Depends(get_authenticated)) -> User:
    """Return only the user for endpoints that do not need the session row."""
    return user[0]


def get_current_admin(user: tuple[User, AuthSession] = Depends(get_authenticated)) -> User:
    """Require the authenticated user to have the admin role."""
    if user[0].role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administratorrechte erforderlich.",
        )
    return user[0]