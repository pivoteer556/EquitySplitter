"""totpCredentials: authenticator-app secrets for institution users

Revision ID: 0010_totp_credentials
Revises: 0009_property_listings
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010_totp_credentials"
down_revision: str | None = "0009_property_listings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "totpCredentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "institutionUserId",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutionUsers.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("secretEncrypted", sa.Text(), nullable=False),
        sa.Column("confirmedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lastUsedStep", sa.BigInteger(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("totpCredentials")
