from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PropertyListingCreate(BaseModel):
    """No status: a new listing is always a draft."""

    model_config = ConfigDict(extra="forbid")

    askingPrice: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: Decimal | None = Field(default=None, ge=0, max_digits=3, decimal_places=1)
    squareFeet: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=5000)


class PropertyListingRead(BaseModel):
    """Officer view: ids are fine here."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    propertyId: UUID
    status: str
    askingPrice: Decimal
    bedrooms: int | None
    bathrooms: Decimal | None
    squareFeet: int | None
    description: str | None
    listedAt: datetime | None
    delistedAt: datetime | None
    createdAt: datetime
