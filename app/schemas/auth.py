import re

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

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
