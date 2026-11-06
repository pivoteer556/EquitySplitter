"""rate limit hit counters shared across replicas

Revision ID: 0004_rate_limit_hits
Revises: 0003_widen_password_hash
Create Date: 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_rate_limit_hits"
down_revision: str | None = "0003_widen_password_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rateLimitHits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("expiresAt", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rateLimitHits_key_expiresAt", "rateLimitHits", ["key", "expiresAt"])
    op.create_index("ix_rateLimitHits_expiresAt", "rateLimitHits", ["expiresAt"])


def downgrade() -> None:
    op.drop_index("ix_rateLimitHits_expiresAt", table_name="rateLimitHits")
    op.drop_index("ix_rateLimitHits_key_expiresAt", table_name="rateLimitHits")
    op.drop_table("rateLimitHits")
