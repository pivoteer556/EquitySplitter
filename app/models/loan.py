import uuid
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    propertyId: Mapped[uuid.UUID] = mapped_column(
        "propertyId",
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    loanAmount: Mapped[float] = mapped_column("loanAmount", Numeric(12, 2), nullable=False)
    currentBalance: Mapped[float] = mapped_column("currentBalance", Numeric(12, 2), nullable=False)
    monthlyPayment: Mapped[float] = mapped_column("monthlyPayment", Numeric(12, 2), nullable=False)
    dynamicBillingEnabled: Mapped[bool] = mapped_column("dynamicBillingEnabled", Boolean, nullable=False, default=False)
    interestRatePercent: Mapped[Decimal | None] = mapped_column("interestRatePercent", Numeric(6, 3), nullable=True)
    termMonths: Mapped[int | None] = mapped_column("termMonths", Integer, nullable=True)
    createdAt: Mapped[DateTime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    property = relationship("Property", back_populates="loan")
