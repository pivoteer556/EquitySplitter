from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PropertyAgreementCreate(BaseModel):
    noticeDays: int = Field(gt=0)
    valuationMethod: str
    partialClaimMethod: str


class PropertyAgreementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    propertyId: UUID
    noticeDays: int
    valuationMethod: str
    partialClaimMethod: str
    effectiveAt: datetime | None