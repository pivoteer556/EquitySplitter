"""widen passwordHash for argon2 encoded hashes

Revision ID: 0003_widen_password_hash
Revises: 0002_auth_and_invariants
Create Date: 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_widen_password_hash"
down_revision: str | None = "0002_auth_and_invariants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Legacy SHA-256 hashes (64 hex chars) stay valid and are re-hashed with argon2id on next login.
    for table in ("users", "institutionUsers"):
        op.alter_column(
            table,
            "passwordHash",
            existing_type=sa.String(length=64),
            type_=sa.String(length=255),
            existing_nullable=True,
        )


def downgrade() -> None:
    # Argon2 hashes cannot fit in 64 chars; affected accounts must reset their password.
    for table in ("users", "institutionUsers"):
        op.execute(
            f'UPDATE "{table}" SET "passwordHash" = NULL, "passwordSalt" = NULL WHERE length("passwordHash") > 64'
        )
        op.alter_column(
            table,
            "passwordHash",
            existing_type=sa.String(length=255),
            type_=sa.String(length=64),
            existing_nullable=True,
        )
