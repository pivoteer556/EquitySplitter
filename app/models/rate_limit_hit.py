import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RateLimitHit(Base):
    """One counted attempt. `key` is a SHA-256 of the caller's key, so no email/IP is stored."""

    __tablename__ = "rateLimitHits"
    __table_args__ = (Index("ix_rateLimitHits_key_expiresAt", "key", "expiresAt"), Index("ix_rateLimitHits_expiresAt", "expiresAt"))

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    # When this attempt stops counting. Stored per row so limiters with different windows can share the table.
    expiresAt: Mapped[datetime] = mapped_column("expiresAt", DateTime(timezone=True), nullable=False)
