import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

# The one place the vocabulary lives. Stored as text, not a database enum, so new stages need no migration.
LISTING_STATUSES = ("draft", "listed", "withdrawn", "sold")

_LISTED = text("status = 'listed'")


class PropertyListing(Base):
    __tablename__ = "propertyListings"
    __table_args__ = (
        # At most one live listing per property; any number of drafts, withdrawn and sold rows.
        Index(
            "ux_propertyListings_one_listed", "propertyId", unique=True, postgresql_where=_LISTED, sqlite_where=_LISTED
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    propertyId: Mapped[uuid.UUID] = mapped_column(
        "propertyId", UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft", server_default="draft")
    askingPrice: Mapped[float] = mapped_column("askingPrice", Numeric(12, 2), nullable=False)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[float | None] = mapped_column(Numeric(3, 1), nullable=True)
    squareFeet: Mapped[int | None] = mapped_column("squareFeet", Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    listedAt: Mapped[DateTime | None] = mapped_column("listedAt", DateTime(timezone=True), nullable=True)
    delistedAt: Mapped[DateTime | None] = mapped_column("delistedAt", DateTime(timezone=True), nullable=True)
    createdAt: Mapped[DateTime] = mapped_column(
        "createdAt", DateTime(timezone=True), nullable=False, server_default=func.now()
    )
