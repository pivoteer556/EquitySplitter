import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RecoveryCode(Base):
    """A one-time sign-in code for an officer who lost their authenticator. Only a keyed hash is stored; usedAt set =
    spent. Eight rows are minted when the authenticator is first confirmed."""

    __tablename__ = "recoveryCodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institutionUserId: Mapped[uuid.UUID] = mapped_column(
        "institutionUserId",
        UUID(as_uuid=True),
        ForeignKey("institutionUsers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    codeHash: Mapped[str] = mapped_column("codeHash", String(64), nullable=False)  # hex HMAC-SHA256
    usedAt: Mapped[datetime | None] = mapped_column("usedAt", DateTime(timezone=True), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False, server_default=func.now()
    )
