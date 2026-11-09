import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TotpCredential(Base):
    """An institution user's authenticator-app secret. One row per user; confirmedAt NULL = enrolment not finished."""

    __tablename__ = "totpCredentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institutionUserId: Mapped[uuid.UUID] = mapped_column(
        "institutionUserId",
        UUID(as_uuid=True),
        ForeignKey("institutionUsers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Fernet token of the base32 secret; the plaintext secret is shown once at enrolment and never stored.
    secretEncrypted: Mapped[str] = mapped_column("secretEncrypted", Text, nullable=False)
    confirmedAt: Mapped[datetime | None] = mapped_column("confirmedAt", DateTime(timezone=True), nullable=True)
    # Highest time step already accepted: a code is single use, so a step <= this is a replay.
    lastUsedStep: Mapped[int | None] = mapped_column("lastUsedStep", BigInteger, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False, server_default=func.now()
    )
