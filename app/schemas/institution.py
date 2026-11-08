from datetime import datetime
from typing import Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

# The one vocabulary of professional roles (validated on create, filtered on the directory).
ProfessionalRole = Literal["loan_officer", "underwriter", "broker"]
PROFESSIONAL_ROLES: tuple[str, ...] = get_args(ProfessionalRole)


class InstitutionCreate(BaseModel):
    name: str


class InstitutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    createdAt: datetime


class InstitutionUserCreate(BaseModel):
    # Officers never choose a password: they activate through a one-time link. extra="forbid" makes a sent
    # `password` a 422 rather than silently ignoring it (same convention as PropertyUpdate).
    model_config = ConfigDict(extra="forbid")

    institutionId: UUID
    name: str
    email: EmailStr
    role: ProfessionalRole = "loan_officer"


class InstitutionUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institutionId: UUID
    name: str
    email: EmailStr
    role: str
    createdAt: datetime


class InstitutionUserCreated(InstitutionUserRead):
    activationToken: str
    activationPath: str
