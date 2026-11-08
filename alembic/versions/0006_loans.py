"""loans table (one per property), backfilled from properties; properties' loan columns stay for now

Revision ID: 0006_loans
Revises: 0005_password_hash_not_null
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_loans"
down_revision: str | None = "0005_password_hash_not_null"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "loans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "propertyId",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("loanAmount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currentBalance", sa.Numeric(12, 2), nullable=False),
        sa.Column("monthlyPayment", sa.Numeric(12, 2), nullable=False),
        sa.Column("dynamicBillingEnabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # gen_random_uuid() is built into PostgreSQL 13+.
    op.execute(
        'INSERT INTO "loans" ("id", "propertyId", "loanAmount", "currentBalance", "monthlyPayment", '
        '"dynamicBillingEnabled") '
        'SELECT gen_random_uuid(), "id", "loanAmount", "currentBalance", "monthlyPayment", "dynamicBillingEnabled" '
        'FROM "properties"'
    )


def downgrade() -> None:
    op.drop_table("loans")
