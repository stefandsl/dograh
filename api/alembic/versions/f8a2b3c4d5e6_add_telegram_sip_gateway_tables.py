"""add telegram sip gateway tables

Revision ID: f8a2b3c4d5e6
Revises: 4c1f1e3e8ef2
Create Date: 2026-05-21 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8a2b3c4d5e6"
down_revision: Union[str, None] = "4c1f1e3e8ef2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_sip_gateway_configurations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("gateway_provider_type", sa.String(length=32), nullable=False),
        sa.Column("credentials", sa.JSON(), nullable=False),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "name",
            name="uq_telegram_sip_gateway_configurations_org_name",
        ),
    )
    op.create_index(
        "ix_telegram_sip_gateway_configurations_org",
        "telegram_sip_gateway_configurations",
        ["organization_id"],
    )

    op.create_table(
        "telegram_sip_call_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("configuration_id", sa.Integer(), nullable=False),
        sa.Column("gateway_call_id", sa.String(length=128), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("destination", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["telegram_sip_gateway_configurations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telegram_sip_call_logs_org",
        "telegram_sip_call_logs",
        ["organization_id"],
    )
    op.create_index(
        "ix_telegram_sip_call_logs_config",
        "telegram_sip_call_logs",
        ["configuration_id"],
    )
    op.create_index(
        op.f("ix_telegram_sip_call_logs_gateway_call_id"),
        "telegram_sip_call_logs",
        ["gateway_call_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_telegram_sip_call_logs_gateway_call_id"),
        table_name="telegram_sip_call_logs",
    )
    op.drop_index("ix_telegram_sip_call_logs_config", table_name="telegram_sip_call_logs")
    op.drop_index("ix_telegram_sip_call_logs_org", table_name="telegram_sip_call_logs")
    op.drop_table("telegram_sip_call_logs")
    op.drop_index(
        "ix_telegram_sip_gateway_configurations_org",
        table_name="telegram_sip_gateway_configurations",
    )
    op.drop_table("telegram_sip_gateway_configurations")
