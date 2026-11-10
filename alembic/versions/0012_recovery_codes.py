"""recoveryCodes: one-time sign-in codes for officers who lost their authenticator

Revision ID: 0012_recovery_codes
Revises: 0011_user_platform_admin
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012_recovery_codes"
down_revision: str | None = "0011_user_platform_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recoveryCodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "institutionUserId",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutionUsers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("codeHash", sa.String(64), nullable=False),
        sa.Column("usedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_recoveryCodes_institutionUserId", "recoveryCodes", ["institutionUserId"])


def downgrade() -> None:
    op.drop_index("ix_recoveryCodes_institutionUserId", table_name="recoveryCodes")
    op.drop_table("recoveryCodes")
