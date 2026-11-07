import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EquityLedger(Base):
    __tablename__ = "equityLedger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userPropertyId: Mapped[uuid.UUID] = mapped_column(
        "userPropertyId", UUID(as_uuid=True), ForeignKey("userProperties.id", ondelete="CASCADE"), nullable=False
    )
    cycleId: Mapped[uuid.UUID] = mapped_column(
        "cycleId", UUID(as_uuid=True), ForeignKey("paymentCycles.id", ondelete="CASCADE"), nullable=False
    )
    baseEquityDelta: Mapped[float] = mapped_column("baseEquityDelta", Numeric(12, 2), nullable=False)
    bonusEquityDelta: Mapped[float] = mapped_column("bonusEquityDelta", Numeric(12, 2), nullable=False, default=0)
    runningBalance: Mapped[float] = mapped_column("runningBalance", Numeric(12, 2), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False, server_default=func.now()
    )
