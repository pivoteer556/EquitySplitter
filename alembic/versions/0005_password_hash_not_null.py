"""passwordHash NOT NULL; users.passwordSetAt marks "invited, password not yet set"

Revision ID: 0005_password_hash_not_null
Revises: 0004_rate_limit_hits
Create Date: 2026-11-07
"""

import secrets
from collections.abc import Sequence

import sqlalchemy as sa
from argon2 import PasswordHasher

from alembic import op

revision: str = "0005_password_hash_not_null"
down_revision: str | None = "0004_rate_limit_hits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("passwordSetAt", sa.DateTime(timezone=True), nullable=True))
    op.execute('UPDATE "users" SET "passwordSetAt" = now() WHERE "passwordHash" IS NOT NULL')

    # Hash-less rows (invited, never accepted) get one argon2 hash of a random secret that is discarded here, so no
    # password verifies against it. It is computed in Python, so offline (--sql) rendering needs no database.
    unusable = PasswordHasher().hash(secrets.token_urlsafe(32))
    for table in ("users", "institutionUsers"):
        op.execute(
            sa.text(f'UPDATE "{table}" SET "passwordHash" = :h WHERE "passwordHash" IS NULL').bindparams(h=unusable)
        )
        op.alter_column(table, "passwordHash", existing_type=sa.String(length=255), nullable=False)


def downgrade() -> None:
    # Cannot restore the NULLs: invited users keep their unusable hash (passwordSetAt IS NULL identified them).
    for table in ("users", "institutionUsers"):
        op.alter_column(table, "passwordHash", existing_type=sa.String(length=255), nullable=True)
    op.drop_column("users", "passwordSetAt")
