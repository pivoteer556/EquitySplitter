from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.types import NormalizedEmailStr


class OwnerInviteCreate(BaseModel):
    name: str
    email: NormalizedEmailStr
    maxOwnershipPercent: Decimal | None = Field(default=None, ge=0, le=100)


class UserPropertyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    userId: UUID
    propertyId: UUID
    maxOwnershipPercent: Decimal | None
    createdAt: datetime