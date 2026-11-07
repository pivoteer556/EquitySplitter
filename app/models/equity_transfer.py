import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EquityTransfer(Base):
    __tablename__ = "equityTransfers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userPropertyId: Mapped[uuid.UUID] = mapped_column(
        "userPropertyId", UUID(as_uuid=True), ForeignKey("userProperties.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    askingPrice: Mapped[float] = mapped_column("askingPrice", Numeric(12, 2), nullable=False)
    sharePercent: Mapped[float] = mapped_column("sharePercent", Numeric(5, 2), nullable=False)
    noticeGivenAt: Mapped[datetime] = mapped_column("noticeGivenAt", DateTime(timezone=True), nullable=False)
    transferredAt: Mapped[datetime | None] = mapped_column("transferredAt", DateTime(timezone=True), nullable=True)
