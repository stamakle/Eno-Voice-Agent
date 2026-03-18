from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuthUser(BaseModel):
    user_id: str = Field(min_length=1, max_length=120)
    learner_id: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=120)
    email_verified: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class AuthSession(BaseModel):
    token: str = Field(min_length=20, max_length=400)
    refresh_token: str = Field(min_length=20, max_length=400)
    user: AuthUser
    expires_at: datetime
    refresh_expires_at: datetime
    email_verification_required: bool = False
    debug_email_verification_token: str | None = None


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=20, max_length=4096)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=400)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=20, max_length=400)


class ResendVerificationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=20, max_length=400)
    new_password: str = Field(min_length=8, max_length=200)


class AuthMessageResponse(BaseModel):
    status: str = "ok"
    message: str
    debug_token: str | None = None


class AuthSessionSummary(BaseModel):
    session_id: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    refresh_expires_at: datetime
    revoked_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    current: bool = False
