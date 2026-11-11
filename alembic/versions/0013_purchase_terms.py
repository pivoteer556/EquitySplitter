"""propertyPurchases (one per property, stage timestamps), loan rate and term, each owner's down payment

Revision ID: 0013_purchase_terms
Revises: 0012_recovery_codes
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_purchase_terms"
down_revision: str | None = "0012_recovery_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "propertyPurchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "propertyId",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("purchasePrice", sa.Numeric(12, 2), nullable=False),
        sa.Column("closingDate", sa.Date(), nullable=True),
        sa.Column("applicationFiledAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("intentToProceedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('"purchasePrice" > 0', name="ck_propertyPurchases_price"),
        # a stage cannot be set without the one before it
        sa.CheckConstraint(
            '"intentToProceedAt" IS NULL OR "applicationFiledAt" IS NOT NULL',
            name="ck_propertyPurchases_itp_needs_application",
        ),
        sa.CheckConstraint(
            '"closedAt" IS NULL OR "intentToProceedAt" IS NOT NULL', name="ck_propertyPurchases_closed_needs_itp"
        ),
    )
    # Nullable: existing rows have no values.
    op.add_column("loans", sa.Column("interestRatePercent", sa.Numeric(6, 3), nullable=True))
    op.add_column("loans", sa.Column("termMonths", sa.Integer(), nullable=True))
    op.add_column("userProperties", sa.Column("downPaymentAmount", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("userProperties", "downPaymentAmount")
    op.drop_column("loans", "termMonths")
    op.drop_column("loans", "interestRatePercent")
    op.drop_table("propertyPurchases")
