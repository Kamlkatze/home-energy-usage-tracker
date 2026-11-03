from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuthSession, User
from ..models.user import UserRole
from ..schemas.user import UserAdminResponse, UserAdminUpdate, UserCreate
from ..security import PasswordStrengthError, hash_password, validate_password_strength
from .deps import get_current_admin

router = APIRouter()


def _get_target_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Benutzer nicht gefunden.",
        )
    return user


def _count_active_admins(db: Session, exclude_user_id: int | None = None) -> int:
    query = db.query(User).filter(
        User.role == UserRole.ADMIN,
        User.is_active.is_(True),
    )
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.count()


def _validate_password(user: User, password: str) -> None:
    try:
        validate_password_strength(password, mfa_enabled=user.totp_enabled)
    except PasswordStrengthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/users")
def list_users(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[UserAdminResponse]:
    """List all users (admin only)."""
    return [UserAdminResponse.model_validate(u) for u in db.query(User).order_by(User.id).all()]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> UserAdminResponse:
    """Create a new user (admin only)."""
    if db.query(User).filter(User.username == body.username).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dieser Benutzername ist bereits vergeben.",
        )
    # New users have no TOTP yet, so the without-MFA minimum applies
    try:
        validate_password_strength(body.password, mfa_enabled=False)
    except PasswordStrengthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserAdminResponse.model_validate(user)


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    body: UserAdminUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> UserAdminResponse:
    """Update role, activation state, password or TOTP enrollment of a user.

    Safety rules:
    - An admin cannot demote or deactivate themselves.
    - The last active admin cannot be demoted or deactivated.
    """
    target = _get_target_user(db, user_id)

    if body.new_password is not None:
        _validate_password(target, body.new_password)

    if body.role is not None and body.role != target.role:
        if target.id == admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Die eigene Rolle kann nicht geändert werden.",
            )
        if target.role == UserRole.ADMIN and _count_active_admins(db) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Der letzte aktive Administrator kann nicht entfernt werden.",
            )

    if body.is_active is False and target.is_active:
        if target.id == admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Das eigene Konto kann nicht deaktiviert werden.",
            )
        if target.role == UserRole.ADMIN and _count_active_admins(db) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Der letzte aktive Administrator kann nicht deaktiviert werden.",
            )

    if body.role is not None:
        target.role = body.role
    if body.is_active is not None:
        target.is_active = body.is_active
    if body.new_password is not None:
        target.password_hash = hash_password(body.new_password)
        # Password reset by admin invalidates all sessions of the target
        for session in db.query(AuthSession).filter(AuthSession.user_id == target.id).all():
            db.delete(session)
    if body.reset_totp:
        target.totp_secret = None
        target.totp_enabled = False
    db.commit()
    db.refresh(target)
    return UserAdminResponse.model_validate(target)