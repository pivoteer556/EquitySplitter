"""institutionUsers.passwordSetAt marks "created, password not yet set" (officer activation links)

Revision ID: 0008_institution_password_set_at
Revises: 0007_connection_requests
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_institution_password_set_at"
down_revision: str | None = "0007_connection_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("institutionUsers", sa.Column("passwordSetAt", sa.DateTime(timezone=True), nullable=True))
    # Every existing officer chose a password, so they are all "already set" and unaffected.
    op.execute('UPDATE "institutionUsers" SET "passwordSetAt" = now()')


def downgrade() -> None:
    op.drop_column("institutionUsers", "passwordSetAt")
