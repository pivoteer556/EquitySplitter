from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.property_listing import LISTING_STATUSES


class PropertyListingCreate(BaseModel):
    """No status: a new listing is always a draft."""

    model_config = ConfigDict(extra="forbid")

    askingPrice: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: Decimal | None = Field(default=None, ge=0, max_digits=3, decimal_places=1)
    squareFeet: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=5000)


class PropertyListingUpdate(BaseModel):
    """Marketing fields only; same rules as create. Send at least one; null clears an optional field."""

    model_config = ConfigDict(extra="forbid")

    askingPrice: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    bedrooms: int | None = Field(default=None, ge=0)
    bathrooms: Decimal | None = Field(default=None, ge=0, max_digits=3, decimal_places=1)
    squareFeet: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def _check(self):
        if not self.model_fields_set:
            raise ValueError("Send at least one field to change")
        if "askingPrice" in self.model_fields_set and self.askingPrice is None:
            raise ValueError("askingPrice cannot be cleared")
        return self


class PropertyListingTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: str

    @field_validator("to")
    @classmethod
    def _known_status(cls, v: str) -> str:
        if v not in LISTING_STATUSES:
            raise ValueError(f"to must be one of {', '.join(LISTING_STATUSES)}")
        return v


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
