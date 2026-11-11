from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.services.purchase import PurchaseStage


class PurchaseRead(BaseModel):
    """Purchase terms and stage. Always present: with no purchase row the stage is `listed` and the rest is null.
    The loan terms come from the Loan row (null when unset)."""

    stage: PurchaseStage
    purchasePrice: Decimal | None = None
    closingDate: date | None = None
    applicationFiledAt: datetime | None = None
    intentToProceedAt: datetime | None = None
    closedAt: datetime | None = None
    interestRatePercent: Decimal | None = None
    termMonths: int | None = None


class ListingSummaryRead(BaseModel):
    """The listing facts a buyer may read (buyers have no listing routes)."""

    askingPrice: Decimal
    bedrooms: int | None
    bathrooms: Decimal | None
    squareFeet: int | None
    description: str | None
