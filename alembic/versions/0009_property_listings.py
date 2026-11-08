"""propertyListings: marketing data per property, many over time, at most one 'listed' at a time

Revision ID: 0009_property_listings
Revises: 0008_institution_password_set_at
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_property_listings"
down_revision: str | None = "0008_institution_password_set_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "propertyListings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "propertyId",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Text, not a database enum: sale stages will grow, and adding one must not need a migration.
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("askingPrice", sa.Numeric(12, 2), nullable=False),
        sa.Column("bedrooms", sa.Integer(), nullable=True),
        sa.Column("bathrooms", sa.Numeric(3, 1), nullable=True),
        sa.Column("squareFeet", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("listedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delistedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_propertyListings_propertyId", "propertyListings", ["propertyId"])
    op.create_index(
        "ux_propertyListings_one_listed",
        "propertyListings",
        ["propertyId"],
        unique=True,
        postgresql_where=sa.text("status = 'listed'"),
    )


def downgrade() -> None:
    op.drop_index("ux_propertyListings_one_listed", table_name="propertyListings")
    op.drop_index("ix_propertyListings_propertyId", table_name="propertyListings")
    op.drop_table("propertyListings")
