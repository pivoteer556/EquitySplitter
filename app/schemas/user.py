from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.types import NormalizedEmailStr


class UserCreate(BaseModel):
    name: str
    email: NormalizedEmailStr


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    createdAt: datetime