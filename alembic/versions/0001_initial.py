"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "institutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "institutionUsers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("institutionId", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_institutionUsers_email", "institutionUsers", ["email"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "properties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("institutionId", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=False),
        sa.Column("loanAmount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currentBalance", sa.Numeric(12, 2), nullable=False),
        sa.Column("monthlyPayment", sa.Numeric(12, 2), nullable=False),
        sa.Column("dynamicBillingEnabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "propertyAgreements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("propertyId", postgresql.UUID(as_uuid=True), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("noticeDays", sa.Integer(), nullable=False),
        sa.Column("valuationMethod", sa.String(length=50), nullable=False),
        sa.Column("partialClaimMethod", sa.String(length=50), nullable=False),
        sa.Column("effectiveAt", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("propertyId", name="uq_propertyAgreements_propertyId"),
    )

    op.create_table(
        "userProperties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("userId", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("propertyId", postgresql.UUID(as_uuid=True), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("maxOwnershipPercent", sa.Numeric(5, 2), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "ownerAcknowledgements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agreementId", postgresql.UUID(as_uuid=True), sa.ForeignKey("propertyAgreements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("userPropertyId", postgresql.UUID(as_uuid=True), sa.ForeignKey("userProperties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signedAt", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "paymentCycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("userPropertyId", postgresql.UUID(as_uuid=True), sa.ForeignKey("userProperties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dueDate", sa.Date(), nullable=False),
        sa.Column("equityDue", sa.Numeric(12, 2), nullable=False),
        sa.Column("interestDue", sa.Numeric(12, 2), nullable=False),
        sa.Column("insuranceDue", sa.Numeric(12, 2), nullable=False),
        sa.Column("hoaDue", sa.Numeric(12, 2), nullable=True),
        sa.Column("otherDue", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cycleId", postgresql.UUID(as_uuid=True), sa.ForeignKey("paymentCycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amountPaid", sa.Numeric(12, 2), nullable=False),
        sa.Column("paidAt", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "equityLedger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("userPropertyId", postgresql.UUID(as_uuid=True), sa.ForeignKey("userProperties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cycleId", postgresql.UUID(as_uuid=True), sa.ForeignKey("paymentCycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("baseEquityDelta", sa.Numeric(12, 2), nullable=False),
        sa.Column("bonusEquityDelta", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("runningBalance", sa.Numeric(12, 2), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_equityLedger_userPropertyId_createdAt", "equityLedger", ["userPropertyId", "createdAt"])

    op.create_table(
        "equityTransfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("userPropertyId", postgresql.UUID(as_uuid=True), sa.ForeignKey("userProperties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("askingPrice", sa.Numeric(12, 2), nullable=False),
        sa.Column("sharePercent", sa.Numeric(5, 2), nullable=False),
        sa.Column("noticeGivenAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transferredAt", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "transferClaims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("transferId", postgresql.UUID(as_uuid=True), sa.ForeignKey("equityTransfers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("userPropertyId", postgresql.UUID(as_uuid=True), sa.ForeignKey("userProperties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claimedPercent", sa.Numeric(5, 2), nullable=False),
        sa.Column("claimedAt", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("transferClaims")
    op.drop_table("equityTransfers")
    op.drop_index("ix_equityLedger_userPropertyId_createdAt", table_name="equityLedger")
    op.drop_table("equityLedger")
    op.drop_table("payments")
    op.drop_table("paymentCycles")
    op.drop_table("ownerAcknowledgements")
    op.drop_table("userProperties")
    op.drop_table("propertyAgreements")
    op.drop_table("properties")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_institutionUsers_email", table_name="institutionUsers")
    op.drop_table("institutionUsers")
    op.drop_table("institutions")