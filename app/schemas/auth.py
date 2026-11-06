import re

from pydantic import BaseModel, EmailStr, field_validator

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
    institutionName: str
    officerName: str
    officerEmail: EmailStr
    officerPassword: str

    @field_validator("officerEmail")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not EMAIL_PATTERN.match(email):
            raise ValueError("Invalid email format")
        return email


class InstitutionBootstrapResponse(BaseModel):
    accessToken: str
    tokenType: str = "Bearer"
    institution: InstitutionRead
    institutionUser: InstitutionUserRead
