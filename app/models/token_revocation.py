import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TokenRevocation(Base):
    __tablename__ = "tokenRevocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institutionUserId: Mapped[uuid.UUID] = mapped_column("institutionUserId", UUID(as_uuid=True), ForeignKey("institutionUsers.id", ondelete="CASCADE"), nullable=False)
    revokedAt: Mapped[datetime] = mapped_column("revokedAt", DateTime(timezone=True), nullable=False, server_default=func.now())
    revokedBy: Mapped[uuid.UUID | None] = mapped_column("revokedBy", UUID(as_uuid=True), ForeignKey("institutionUsers.id", ondelete="SET NULL"), nullable=True)
