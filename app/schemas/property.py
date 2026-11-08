from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

LoanAmount = Annotated[Decimal, Field(gt=0)]
CurrentBalance = Annotated[Decimal, Field(ge=0)]
MonthlyPayment = Annotated[Decimal, Field(gt=0)]


class PropertyCreate(BaseModel):
    institutionId: UUID
    address: str
    loanAmount: LoanAmount
    currentBalance: CurrentBalance
    monthlyPayment: MonthlyPayment
    dynamicBillingEnabled: bool = False


class PropertyUpdate(BaseModel):
    """Partial update: only fields present in the body change. Unknown fields, nulls and an empty body are 422."""

    model_config = ConfigDict(extra="forbid")

    address: Annotated[str, Field(min_length=1)] | None = None
    loanAmount: LoanAmount | None = None
    currentBalance: CurrentBalance | None = None
    monthlyPayment: MonthlyPayment | None = None
    dynamicBillingEnabled: bool | None = None

    @model_validator(mode="after")
    def _non_empty_and_no_nulls(self) -> "PropertyUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        nulls = [f for f in self.model_fields_set if getattr(self, f) is None]
        if nulls:
            raise ValueError(f"Fields cannot be null: {', '.join(sorted(nulls))}")
        return self


class PropertyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institutionId: UUID
    address: str
    loanAmount: Decimal
    currentBalance: Decimal
    monthlyPayment: Decimal
    dynamicBillingEnabled: bool
    status: str
    createdAt: datetime