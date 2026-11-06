from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.user import UserRole


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=1, max_length=512)
    role: UserRole = UserRole.USER


class UserAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole | None = None
    is_active: bool | None = None
    # Admin-triggered password reset
    new_password: str | None = Field(default=None, min_length=1, max_length=512)
    # Clear TOTP enrollment (lost authenticator recovery)
    reset_totp: bool = False


class UserAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
    is_active: bool
    totp_enabled: bool
    created_at: datetime