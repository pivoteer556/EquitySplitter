"""users.isPlatformAdmin: platform admin account kind (no institution)

Revision ID: 0011_user_platform_admin
Revises: 0010_totp_credentials
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_user_platform_admin"
down_revision: str | None = "0010_totp_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("isPlatformAdmin", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "isPlatformAdmin")
