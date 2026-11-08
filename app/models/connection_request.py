import uuid
from datetime import datetime
from typing import Literal, get_args

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

# The one vocabulary of request states; only "pending" is produced so far (accept/decline/cancel come later).
ConnectionStatus = Literal["pending", "accepted", "declined", "cancelled"]
CONNECTION_STATUSES: tuple[str, ...] = get_args(ConnectionStatus)


class ConnectionRequest(Base):
    __tablename__ = "connectionRequests"
    __table_args__ = (
        UniqueConstraint(
            "buyerId", "professionalId", "propertyId", name="uq_connectionRequests_buyer_professional_property"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    buyerId: Mapped[uuid.UUID] = mapped_column(
        "buyerId", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    professionalId: Mapped[uuid.UUID] = mapped_column(
        "professionalId", UUID(as_uuid=True), ForeignKey("institutionUsers.id", ondelete="CASCADE"), nullable=False
    )
    propertyId: Mapped[uuid.UUID] = mapped_column(
        "propertyId", UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    createdAt: Mapped[DateTime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updatedAt: Mapped[datetime | None] = mapped_column("updatedAt", DateTime(timezone=True), nullable=True)
