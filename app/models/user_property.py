import uuid
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class UserProperty(Base):
    __tablename__ = "userProperties"
    __table_args__ = (UniqueConstraint("userId", "propertyId", name="uq_userProperties_user_property"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userId: Mapped[uuid.UUID] = mapped_column(
        "userId", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    propertyId: Mapped[uuid.UUID] = mapped_column(
        "propertyId", UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    maxOwnershipPercent: Mapped[float | None] = mapped_column("maxOwnershipPercent", Numeric(5, 2), nullable=True)
    downPaymentAmount: Mapped[Decimal | None] = mapped_column("downPaymentAmount", Numeric(12, 2), nullable=True)
    createdAt: Mapped[DateTime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user = relationship("User", back_populates="userProperties")
    property = relationship("Property", back_populates="userProperties")
    acknowledgements = relationship("OwnerAcknowledgement", back_populates="userProperty", cascade="all, delete-orphan")
