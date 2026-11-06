import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TransferClaim(Base):
    __tablename__ = "transferClaims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transferId: Mapped[uuid.UUID] = mapped_column("transferId", UUID(as_uuid=True), ForeignKey("equityTransfers.id", ondelete="CASCADE"), nullable=False)
    userPropertyId: Mapped[uuid.UUID] = mapped_column("userPropertyId", UUID(as_uuid=True), ForeignKey("userProperties.id", ondelete="CASCADE"), nullable=False)
    claimedPercent: Mapped[float] = mapped_column("claimedPercent", Numeric(5, 2), nullable=False)
    claimedAt: Mapped[datetime] = mapped_column("claimedAt", DateTime(timezone=True), nullable=False)