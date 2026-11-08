import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institutionId: Mapped[uuid.UUID] = mapped_column(
        "institutionId", UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False
    )
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    loanAmount: Mapped[float] = mapped_column("loanAmount", Numeric(12, 2), nullable=False)
    currentBalance: Mapped[float] = mapped_column("currentBalance", Numeric(12, 2), nullable=False)
    monthlyPayment: Mapped[float] = mapped_column("monthlyPayment", Numeric(12, 2), nullable=False)
    dynamicBillingEnabled: Mapped[bool] = mapped_column("dynamicBillingEnabled", Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending_acknowledgement")
    createdAt: Mapped[DateTime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    institution = relationship("Institution", back_populates="properties")
    agreement = relationship(
        "PropertyAgreement", back_populates="property", uselist=False, cascade="all, delete-orphan"
    )
    loan = relationship("Loan", back_populates="property", uselist=False, cascade="all, delete-orphan")
    userProperties =relationship("UserProperty", back_populates="property", cascade="all, delete-orphan")
    connectionRequests = relationship("ConnectionRequest", cascade="all, delete-orphan", passive_deletes=False)
