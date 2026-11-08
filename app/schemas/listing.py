from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ListingRead(BaseModel):
    """Marketplace view of a pending property: deliberately no loan, agreement, owner or institution data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    address: str
    status: str
    createdAt: datetime
