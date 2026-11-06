"""auth and invariants

Revision ID: 0002_auth_and_invariants
Revises: 0001_initial
Create Date: 2026-05-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_auth_and_invariants"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("passwordHash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("passwordSalt", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("lastTokenIssuedAt", sa.DateTime(timezone=True), nullable=True))

    op.add_column("institutionUsers", sa.Column("passwordHash", sa.String(length=64), nullable=True))
    op.add_column("institutionUsers", sa.Column("passwordSalt", sa.String(length=64), nullable=True))
    op.add_column("institutionUsers", sa.Column("lastTokenIssuedAt", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "tokenRevocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("institutionUserId", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutionUsers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revokedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revokedBy", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutionUsers.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_tokenRevocations_institutionUserId", "tokenRevocations", ["institutionUserId"])

    op.create_table(
        "authSecretState",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("currentSecret", sa.String(length=512), nullable=False),
        sa.Column("previousSecret", sa.String(length=512), nullable=True),
        sa.Column("rotatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_unique_constraint("uq_userProperties_user_property", "userProperties", ["userId", "propertyId"])
    op.create_unique_constraint("uq_ownerAcks_agreement_userProperty", "ownerAcknowledgements", ["agreementId", "userPropertyId"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_property_agreement_update_after_effective()
        RETURNS trigger AS $$
        BEGIN
            IF OLD."effectiveAt" IS NOT NULL THEN
                RAISE EXCEPTION 'property agreement is immutable once effective';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_prevent_property_agreement_update_after_effective
        BEFORE UPDATE ON "propertyAgreements"
        FOR EACH ROW
        EXECUTE FUNCTION prevent_property_agreement_update_after_effective();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_owner_ack_update_after_signed()
        RETURNS trigger AS $$
        BEGIN
            IF OLD."signedAt" IS NOT NULL THEN
                RAISE EXCEPTION 'owner acknowledgement is immutable once signed';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_prevent_owner_ack_update_after_signed
        BEFORE UPDATE ON "ownerAcknowledgements"
        FOR EACH ROW
        EXECUTE FUNCTION prevent_owner_ack_update_after_signed();
        """
    )


def downgrade() -> None:
    op.execute('DROP TRIGGER IF EXISTS tr_prevent_owner_ack_update_after_signed ON "ownerAcknowledgements";')
    op.execute("DROP FUNCTION IF EXISTS prevent_owner_ack_update_after_signed();")
    op.execute('DROP TRIGGER IF EXISTS tr_prevent_property_agreement_update_after_effective ON "propertyAgreements";')
    op.execute("DROP FUNCTION IF EXISTS prevent_property_agreement_update_after_effective();")

    op.drop_constraint("uq_ownerAcks_agreement_userProperty", "ownerAcknowledgements", type_="unique")
    op.drop_constraint("uq_userProperties_user_property", "userProperties", type_="unique")

    op.drop_table("authSecretState")
    op.drop_index("ix_tokenRevocations_institutionUserId", table_name="tokenRevocations")
    op.drop_table("tokenRevocations")

    op.drop_column("institutionUsers", "lastTokenIssuedAt")
    op.drop_column("institutionUsers", "passwordSalt")
    op.drop_column("institutionUsers", "passwordHash")

    op.drop_column("users", "lastTokenIssuedAt")
    op.drop_column("users", "passwordSalt")
    op.drop_column("users", "passwordHash")
