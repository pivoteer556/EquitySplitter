from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.purchase import ListingSummaryRead, PurchaseRead


class AcknowledgementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agreementId: UUID
    userPropertyId: UUID
    signedAt: datetime | None


class OwnerInviteRead(AcknowledgementRead):
    # Subclass so the acknowledge endpoint's response shape is unchanged.
    inviteToken: str | None = None


class PropertyOwnerStatus(BaseModel):
    userPropertyId: UUID
    userId: UUID
    name: str
    email: str
    maxOwnershipPercent: float | None
    signedAt: datetime | None
    # Additive (vertical slice S2). Null = "not set": the share fields are null unless every owner has a down payment.
    downPaymentAmount: Decimal | None = None
    sharePercent: Decimal | None = None
    estimatedMonthlyShare: Decimal | None = None


class PropertyDetailRead(BaseModel):
    property: dict
    agreement: dict | None
    purchase: PurchaseRead
    listing: ListingSummaryRead | None = None  # the live (status listed) listing, else null


class PropertyOwnersRead(BaseModel):
    owners: list[PropertyOwnerStatus]