from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PropertyCreate(BaseModel):
    institutionId: UUID
    address: str
    loanAmount: Decimal = Field(gt=0)
    currentBalance: Decimal = Field(ge=0)
    monthlyPayment: Decimal = Field(gt=0)
    dynamicBillingEnabled: bool = False


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