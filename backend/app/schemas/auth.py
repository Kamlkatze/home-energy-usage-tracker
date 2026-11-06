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


class TotpSetupResponse(BaseModel):
    # Raw secret for manual entry + provisioning URI for QR rendering
    secret: str
    otpauth_url: str


class TotpEnableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=6, max_length=10)


class TotpDisableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Disabling 2FA requires re-authentication (password + valid code)
    password: str = Field(min_length=1, max_length=512)
    code: str = Field(min_length=6, max_length=10)


class TotpStatusResponse(BaseModel):
    enabled: bool
    # True while a setup has been started but not yet confirmed with a
    # valid code - the frontend can offer to continue the enrollment
    pending_setup: bool