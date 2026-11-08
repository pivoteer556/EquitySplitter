"""connectionRequests: a buyer asks a professional (institution user) about a pending property

Revision ID: 0007_connection_requests
Revises: 0006_loans
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_connection_requests"
down_revision: str | None = "0006_loans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connectionRequests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "buyerId", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "professionalId",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutionUsers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "propertyId",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "buyerId", "professionalId", "propertyId", name="uq_connectionRequests_buyer_professional_property"
        ),
    )


def downgrade() -> None:
    op.drop_table("connectionRequests")
