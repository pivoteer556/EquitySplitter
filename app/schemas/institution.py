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
    institutionId: UUID
    name: str
    email: EmailStr
    password: str
    role: ProfessionalRole = "loan_officer"


class InstitutionUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institutionId: UUID
    name: str
    email: EmailStr
    role: str
    createdAt: datetime
