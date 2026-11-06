from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AcknowledgementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agreementId: UUID
    userPropertyId: UUID
    signedAt: datetime | None


class PropertyOwnerStatus(BaseModel):
    userPropertyId: UUID
    userId: UUID
    name: str
    email: str
    maxOwnershipPercent: float | None
    signedAt: datetime | None


class PropertyDetailRead(BaseModel):
    property: dict
    agreement: dict | None


class PropertyOwnersRead(BaseModel):
    owners: list[PropertyOwnerStatus]