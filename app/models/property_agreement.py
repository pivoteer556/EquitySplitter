import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class PropertyAgreement(Base):
    __tablename__ = "propertyAgreements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    propertyId: Mapped[uuid.UUID] = mapped_column("propertyId", UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, unique=True)
    noticeDays: Mapped[int] = mapped_column("noticeDays", Integer, nullable=False)
    valuationMethod: Mapped[str] = mapped_column("valuationMethod", String(50), nullable=False)
    partialClaimMethod: Mapped[str] = mapped_column("partialClaimMethod", String(50), nullable=False)
    effectiveAt: Mapped[datetime | None] = mapped_column("effectiveAt", DateTime(timezone=True), nullable=True)

    property = relationship("Property", back_populates="agreement")
    acknowledgements = relationship("OwnerAcknowledgement", back_populates="agreement", cascade="all, delete-orphan")