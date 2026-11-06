from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


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
    role: str = "loan_officer"


class InstitutionUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institutionId: UUID
    name: str
    email: EmailStr
    role: str
    createdAt: datetime
