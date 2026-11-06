import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class PaymentCycle(Base):
    __tablename__ = "paymentCycles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userPropertyId: Mapped[uuid.UUID] = mapped_column("userPropertyId", UUID(as_uuid=True), ForeignKey("userProperties.id", ondelete="CASCADE"), nullable=False)
    dueDate: Mapped[date] = mapped_column("dueDate", Date, nullable=False)
    equityDue: Mapped[float] = mapped_column("equityDue", Numeric(12, 2), nullable=False)
    interestDue: Mapped[float] = mapped_column("interestDue", Numeric(12, 2), nullable=False)
    insuranceDue: Mapped[float] = mapped_column("insuranceDue", Numeric(12, 2), nullable=False)
    hoaDue: Mapped[float | None] = mapped_column("hoaDue", Numeric(12, 2), nullable=True)
    otherDue: Mapped[float | None] = mapped_column("otherDue", Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")

    payments = relationship("Payment", back_populates="cycle", cascade="all, delete-orphan")