import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class InstitutionUser(Base):
    __tablename__ = "institutionUsers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institutionId: Mapped[uuid.UUID] = mapped_column(
        "institutionId", UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    passwordHash: Mapped[str] = mapped_column("passwordHash", String(255), nullable=False)
    passwordSalt: Mapped[str | None] = mapped_column("passwordSalt", String(64), nullable=True)
    lastTokenIssuedAt: Mapped[datetime | None] = mapped_column(
        "lastTokenIssuedAt", DateTime(timezone=True), nullable=True
    )
    passwordSetAt: Mapped[datetime | None] = mapped_column("passwordSetAt", DateTime(timezone=True), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="loan_officer")
    createdAt: Mapped[DateTime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    institution = relationship("Institution", back_populates="institutionUsers")
