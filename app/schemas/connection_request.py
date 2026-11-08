from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.connection_request import ConnectionStatus


class ConnectionRequestCreate(BaseModel):
    professionalId: UUID
    propertyId: UUID
    message: str | None = Field(default=None, max_length=1000)


class ConnectionRequestRead(BaseModel):
    """Buyer view: deliberately no buyer email, institution ids or loan data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    professionalId: UUID
    propertyId: UUID
    status: ConnectionStatus
    message: str | None
    createdAt: datetime


class IncomingConnectionRequestRead(ConnectionRequestRead):
    """Professional view: the same plus the buyer's name (never the email)."""

    buyerName: str
