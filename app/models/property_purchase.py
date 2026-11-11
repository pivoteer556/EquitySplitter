import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class PropertyPurchase(Base):
    """The purchase of one property (one row per property). The stage (listed, application filed, intent to proceed,
    closed) is never stored: it is derived from which timestamps are set (app/services/purchase.py)."""

    __tablename__ = "propertyPurchases"
    __table_args__ = (
        CheckConstraint('"purchasePrice" > 0', name="ck_propertyPurchases_price"),
        # a stage cannot be set without the one before it
        CheckConstraint(
            '"intentToProceedAt" IS NULL OR "applicationFiledAt" IS NOT NULL',
            name="ck_propertyPurchases_itp_needs_application",
        ),
        CheckConstraint(
            '"closedAt" IS NULL OR "intentToProceedAt" IS NOT NULL', name="ck_propertyPurchases_closed_needs_itp"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    propertyId: Mapped[uuid.UUID] = mapped_column(
        "propertyId",
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    purchasePrice: Mapped[Decimal] = mapped_column("purchasePrice", Numeric(12, 2), nullable=False)
    closingDate: Mapped[date | None] = mapped_column("closingDate", Date, nullable=True)  # planned, then actual
    applicationFiledAt: Mapped[datetime | None] = mapped_column(
        "applicationFiledAt", DateTime(timezone=True), nullable=True
    )
    intentToProceedAt: Mapped[datetime | None] = mapped_column(
        "intentToProceedAt", DateTime(timezone=True), nullable=True
    )
    closedAt: Mapped[datetime | None] = mapped_column("closedAt", DateTime(timezone=True), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    property = relationship("Property", back_populates="purchase")
