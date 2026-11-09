import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.institution import InstitutionRead, InstitutionUserRead

EMAIL_PATTERN = re.compile(r"^[^@]+@[^@]+$")


class AuthRegisterRequest(BaseModel):
    name: str
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not EMAIL_PATTERN.match(email):
            raise ValueError("Invalid email format")
        return email


class AuthLoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not EMAIL_PATTERN.match(email):
            raise ValueError("Invalid email format")
        return email


class AuthTokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "Bearer"


class LoginResponse(AuthTokenResponse):
    """Token plus access info, so a client can route from one login response. userType is "user" (owner, buyer or
    platform admin) or "institution_user" (officer); role and institutionId are set for officers only."""

    userType: Literal["user", "institution_user"]
    isPlatformAdmin: bool
    role: str | None = None
    institutionId: UUID | None = None


class SecondFactorChallenge(BaseModel):
    """Returned by POST /auth/login instead of a token when the officer has a confirmed authenticator. The
    challengeToken only works at POST /auth/login/totp."""

    userType: Literal["institution_user"] = "institution_user"
    secondFactorRequired: Literal[True] = True
    challengeToken: str


class LoginTotpRequest(BaseModel):
    challengeToken: str
    code: str = Field(pattern=r"^\d{6}$")


class AcceptInviteRequest(BaseModel):
    token: str
    password: str


class InstitutionRevokeRequest(BaseModel):
    institutionUserId: str | None = None


class InstitutionBootstrapRequest(BaseModel):
    # The first officer activates through a one-time link like every other officer, so a sent `officerPassword`
    # is a 422 rather than silently ignored (same convention as InstitutionUserCreate).
    model_config = ConfigDict(extra="forbid")

    institutionName: str
    officerName: str
    officerEmail: EmailStr

    @field_validator("officerEmail")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not EMAIL_PATTERN.match(email):
            raise ValueError("Invalid email format")
        return email


class InstitutionBootstrapResponse(BaseModel):
    institution: InstitutionRead
    institutionUser: InstitutionUserRead
    activationToken: str
    activationPath: str
