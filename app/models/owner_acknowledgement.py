import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class OwnerAcknowledgement(Base):
    __tablename__ = "ownerAcknowledgements"
    __table_args__ = (UniqueConstraint("agreementId", "userPropertyId", name="uq_ownerAcks_agreement_userProperty"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreementId: Mapped[uuid.UUID] = mapped_column("agreementId", UUID(as_uuid=True), ForeignKey("propertyAgreements.id", ondelete="CASCADE"), nullable=False)
    userPropertyId: Mapped[uuid.UUID] = mapped_column("userPropertyId", UUID(as_uuid=True), ForeignKey("userProperties.id", ondelete="CASCADE"), nullable=False)
    signedAt: Mapped[datetime | None] = mapped_column("signedAt", DateTime(timezone=True), nullable=True)

    agreement = relationship("PropertyAgreement", back_populates="acknowledgements")
    userProperty = relationship("UserProperty", back_populates="acknowledgements")
