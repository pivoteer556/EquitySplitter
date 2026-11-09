import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, false, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    passwordHash: Mapped[str] = mapped_column("passwordHash", String(255), nullable=False)
    # NULL while invited and the password is not yet chosen (passwordHash then holds an unusable hash).
    passwordSetAt: Mapped[datetime | None] = mapped_column("passwordSetAt", DateTime(timezone=True), nullable=True)
    # Platform admin: an account with no institution that may (with the setup token) bootstrap institutions.
    # Distinct from the per-institution ADMIN role planned in backlog 2l. Set only by the operator script.
    isPlatformAdmin: Mapped[bool] = mapped_column(
        "isPlatformAdmin", Boolean, nullable=False, default=False, server_default=false()
    )
    passwordSalt: Mapped[str | None] = mapped_column("passwordSalt", String(64), nullable=True)
    lastTokenIssuedAt: Mapped[datetime | None] = mapped_column(
        "lastTokenIssuedAt", DateTime(timezone=True), nullable=True
    )
    createdAt: Mapped[DateTime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    userProperties = relationship("UserProperty", back_populates="user", cascade="all, delete-orphan")
