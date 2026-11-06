import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    passwordHash: Mapped[str | None] = mapped_column("passwordHash", String(255), nullable=True)
    passwordSalt: Mapped[str | None] = mapped_column("passwordSalt", String(64), nullable=True)
    lastTokenIssuedAt: Mapped[datetime | None] = mapped_column("lastTokenIssuedAt", DateTime(timezone=True), nullable=True)
    createdAt: Mapped[DateTime] = mapped_column("createdAt", DateTime(timezone=True), nullable=False, server_default=func.now())

    userProperties = relationship("UserProperty", back_populates="user", cascade="all, delete-orphan")
