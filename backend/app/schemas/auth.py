from pydantic import BaseModel, ConfigDict, Field

from ..models.user import UserRole


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=512)
    # Optional TOTP code; required (server-side) once TOTP is enabled
    totp_code: str | None = Field(default=None, max_length=10)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
    totp_enabled: bool


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=1, max_length=512)
    # When true, all other sessions of the user are invalidated
    logout_other_sessions: bool = False