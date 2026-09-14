from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("password")
    @classmethod
    def validate_password_strength(
        cls,
        value: str,
    ) -> str:
        if not re.search(r"[A-Z]", value):
            raise ValueError(
                "Password must contain at least one uppercase letter"
            )

        if not re.search(r"[a-z]", value):
            raise ValueError(
                "Password must contain at least one lowercase letter"
            )

        if not re.search(r"\d", value):
            raise ValueError(
                "Password must contain at least one digit"
            )

        if not re.search(r"[^A-Za-z0-9]", value):
            raise ValueError(
                "Password must contain at least one special character"
            )

        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    mfa_code: str | None = Field(
        default=None,
        min_length=6,
        max_length=6,
    )

    @field_validator("mfa_code")
    @classmethod
    def validate_mfa_code(
        cls,
        value: str | None,
    ) -> str | None:
        if value is not None and not value.isdigit():
            raise ValueError(
                "MFA code must contain only digits"
            )

        return value


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(
        min_length=1,
        max_length=4096,
    )


class LogoutRequest(BaseModel):
    refresh_token: str = Field(
        min_length=1,
        max_length=4096,
    )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutResponse(BaseModel):
    message: str


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    message: str


class MFAVerifyRequest(BaseModel):
    code: str = Field(
        min_length=6,
        max_length=6,
    )

    @field_validator("code")
    @classmethod
    def validate_code(
        cls,
        value: str,
    ) -> str:
        if not value.isdigit():
            raise ValueError(
                "MFA code must contain only digits"
            )

        return value


class MFADisableRequest(BaseModel):
    password: str = Field(
        min_length=1,
        max_length=128,
    )
    code: str = Field(
        min_length=6,
        max_length=6,
    )

    @field_validator("code")
    @classmethod
    def validate_disable_code(
        cls,
        value: str,
    ) -> str:
        if not value.isdigit():
            raise ValueError(
                "MFA code must contain only digits"
            )

        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: str
    is_email_verified: bool
    mfa_enabled: bool
    created_at: datetime
    updated_at: datetime


class AuthenticatedUserResponse(UserResponse):
    pass