import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AuthSecretState(Base):
    __tablename__ = "authSecretState"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    currentSecret: Mapped[str] = mapped_column("currentSecret", String(512), nullable=False)
    previousSecret: Mapped[str | None] = mapped_column("previousSecret", String(512), nullable=True)
    rotatedAt: Mapped[datetime] = mapped_column("rotatedAt", DateTime(timezone=True), nullable=False, server_default=func.now())
