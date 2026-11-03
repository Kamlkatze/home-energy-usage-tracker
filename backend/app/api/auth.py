from datetime import UTC, datetime, timedelta

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import AuthSession, User
from ..schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    TotpDisableRequest,
    TotpEnableRequest,
    TotpSetupResponse,
    TotpStatusResponse,
    UserResponse,
)
from ..security import (
    PasswordStrengthError,
    dummy_verify_password,
    generate_session_token,
    hash_password,
    hash_session_token,
    validate_password_strength,
    verify_password,
)
from .deps import get_authenticated, get_current_user

router = APIRouter()

# Generic error message for all credential failures (prevents user
# enumeration, see OWASP Authentication Cheat Sheet).
INVALID_CREDENTIALS = "Ungültiger Benutzername oder Passwort."

# Exponential account lockout: the Nth consecutive failed attempt locks
# the account for 2**N seconds, capped at 15 minutes. The counter is
# bound to the account, not the source IP (per OWASP).
LOCKOUT_MAX_SECONDS = 900

# Allow one 30-second window of clock drift when verifying TOTP codes.
TOTP_VALID_WINDOWS = 1


def _lockout_seconds(failed_login_count: int) -> int:
    # min() of int literals returns Any for mypy without the cast
    return int(min(2**failed_login_count, LOCKOUT_MAX_SECONDS))


def _register_failed_login(db: Session, user: User) -> None:
    user.failed_login_count += 1
    user.locked_until = datetime.now(UTC) + timedelta(
        seconds=_lockout_seconds(user.failed_login_count)
    )
    db.commit()


def _register_successful_login(db: Session, user: User) -> None:
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_LIFETIME_HOURS * 3600,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )


def _verify_totp(user: User, code: str | None) -> bool:
    if not user.totp_enabled or not user.totp_secret:
        return True
    if not code:
        return False
    return pyotp.TOTP(user.totp_secret).verify(code, valid_window=TOTP_VALID_WINDOWS)


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UserResponse:
    """Authenticate with username/password (plus TOTP code if enabled).

    Sets an HttpOnly session cookie. All credential failures use a
    generic error message to prevent user enumeration.
    """
    user = db.query(User).filter(User.username == body.username).first()
    now = datetime.now(UTC)
    if user is None:
        dummy_verify_password()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)

    if user.locked_until is not None and user.locked_until > now:
        # Any attempt while locked (even with the correct password)
        # extends the exponential lockout instead of verifying
        # credentials. This is the OWASP exponential-lockout pattern.
        _register_failed_login(db, user)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Zu viele fehlgeschlagene Anmeldeversuche. "
                "Bitte versuchen Sie es später erneut."
            ),
        )

    if not verify_password(user.password_hash, body.password):
        _register_failed_login(db, user)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)

    if not _verify_totp(user, body.totp_code):
        _register_failed_login(db, user)
        if not body.totp_code:
            # The password was correct but a second factor is required.
            # The frontend shows the TOTP input field in this case.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"message": "Zwei-Faktor-Code erforderlich.", "totp_required": True},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger Zwei-Faktor-Code.",
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)

    _register_successful_login(db, user)
    token = generate_session_token()
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=now + timedelta(hours=settings.SESSION_LIFETIME_HOURS),
        last_used_at=now,
    )
    db.add(auth_session)
    db.commit()
    _set_session_cookie(response, token)
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    """Invalidate the current session server-side and clear the cookie.

    Idempotent: succeeds even without a (valid) session cookie.
    """
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if token:
        auth_session = (
            db.query(AuthSession)
            .filter(AuthSession.token_hash == hash_session_token(token))
            .first()
        )
        if auth_session is not None:
            db.delete(auth_session)
            db.commit()
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user."""
    return UserResponse.model_validate(user)


class PasswordChangeResponse(BaseModel):
    message: str


@router.post("/change-password")
def change_password(
    body: PasswordChangeRequest,
    auth: tuple[User, AuthSession] = Depends(get_authenticated),
    db: Session = Depends(get_db),
) -> PasswordChangeResponse:
    """Change the password of the authenticated user.

    Requires re-authentication with the current password (OWASP).
    """
    user, current_session = auth
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Aktuelles Passwort ist falsch.",
        )
    try:
        validate_password_strength(body.new_password, mfa_enabled=user.totp_enabled)
    except PasswordStrengthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    user.password_hash = hash_password(body.new_password)
    if body.logout_other_sessions:
        for session in (
            db.query(AuthSession)
            .filter(
                AuthSession.user_id == user.id,
                AuthSession.id != current_session.id,
            )
            .all()
        ):
            db.delete(session)
    db.commit()
    return PasswordChangeResponse(message="Passwort wurde geändert.")


@router.get("/totp")
def totp_status(user: User = Depends(get_current_user)) -> TotpStatusResponse:
    """Report whether TOTP is enabled or a setup is pending."""
    return TotpStatusResponse(
        enabled=user.totp_enabled,
        pending_setup=not user.totp_enabled and user.totp_secret is not None,
    )


@router.post("/totp/setup")
def totp_setup(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TotpSetupResponse:
    """Start TOTP enrollment: generate a new secret and provisioning URI.

    The secret is stored but TOTP stays disabled until /totp/enable
    confirms possession of the authenticator with a valid code. Calling
    setup again replaces any pending (unconfirmed) secret.
    """
    if user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zwei-Faktor-Authentifizierung ist bereits aktiviert.",
        )
    secret = pyotp.random_base32()
    user.totp_secret = secret
    db.commit()
    otpauth_url = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.username, issuer_name=settings.TOTP_ISSUER
    )
    return TotpSetupResponse(secret=secret, otpauth_url=otpauth_url)


@router.post("/totp/enable")
def totp_enable(
    body: TotpEnableRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TotpStatusResponse:
    """Confirm TOTP enrollment with a valid code and activate 2FA."""
    if user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zwei-Faktor-Authentifizierung ist bereits aktiviert.",
        )
    if user.totp_secret is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zwei-Faktor-Einrichtung wurde noch nicht gestartet.",
        )
    if not pyotp.TOTP(user.totp_secret).verify(body.code, valid_window=TOTP_VALID_WINDOWS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ungültiger Zwei-Faktor-Code.",
        )
    user.totp_enabled = True
    db.commit()
    return TotpStatusResponse(enabled=True, pending_setup=False)


@router.post("/totp/disable")
def totp_disable(
    body: TotpDisableRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TotpStatusResponse:
    """Deactivate TOTP.

    Sensitive operation: requires re-authentication with the current
    password plus a valid TOTP code (proves both knowledge and
    possession).
    """
    if not user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zwei-Faktor-Authentifizierung ist nicht aktiviert.",
        )
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Aktuelles Passwort ist falsch.",
        )
    if not pyotp.TOTP(user.totp_secret or "").verify(body.code, valid_window=TOTP_VALID_WINDOWS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ungültiger Zwei-Faktor-Code.",
        )
    user.totp_enabled = False
    user.totp_secret = None
    db.commit()
    return TotpStatusResponse(enabled=False, pending_setup=False)