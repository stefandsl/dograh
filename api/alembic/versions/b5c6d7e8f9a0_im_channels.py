"""add im_channels table

ADR-102 + Phase 4a of the CliClaw merge. Stores one row per IM channel
an organisation has enabled. Soft-link to ``api_keys.id`` for the
service-account key the bot uses on its outbound API calls.

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-05-27 23:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "im_channels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        # Fernet ciphertext (string) — encrypted JSON config blob.
        sa.Column("config_encrypted", sa.Text(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "api_key_id",
            sa.Integer(),
            sa.ForeignKey("api_keys.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "type",
            "name",
            name="uq_im_channels_org_type_name",
        ),
    )
    op.create_index(
        "ix_im_channels_org_type_enabled",
        "im_channels",
        ["organization_id", "type", "enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_im_channels_org_type_enabled", table_name="im_channels")
    op.drop_constraint(
        "uq_im_channels_org_type_name", "im_channels", type_="unique"
    )
    op.drop_table("im_channels")
