import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cycleId: Mapped[uuid.UUID] = mapped_column("cycleId", UUID(as_uuid=True), ForeignKey("paymentCycles.id", ondelete="CASCADE"), nullable=False)
    amountPaid: Mapped[float] = mapped_column("amountPaid", Numeric(12, 2), nullable=False)
    paidAt: Mapped[datetime | None] = mapped_column("paidAt", DateTime(timezone=True), nullable=True)

    cycle = relationship("PaymentCycle", back_populates="payments")