"""add whatsapp_sessions table

Phase WhatsApp of the IM channels work. Parallel to ``telegram_sessions``:
one row per (organisation, wa_phone_number) tracks the active workflow,
current run, conversation state, and per-conversation extras (last
inbound message id, language, etc.).

WhatsApp credentials/config live in ``im_channels`` (type='whatsapp')
with the same encrypted-config pattern Telegram uses. This table is the
runtime conversation map.

Revision ID: c7e8f9a0b1c2
Revises: b5c6d7e8f9a0
Create Date: 2026-05-29 00:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c7e8f9a0b1c2"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # The customer's E.164 phone number as received from Meta
        # (e.g. "+393454717205"). Stored without the leading + per Meta's
        # convention — the dispatcher normalises before lookup.
        sa.Column("wa_id", sa.String(32), nullable=False),
        sa.Column(
            "channel_id",
            sa.Integer(),
            sa.ForeignKey("im_channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            sa.ForeignKey("workflows.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "workflow_run_id",
            sa.Integer(),
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "state",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'idle'"),
        ),
        sa.Column(
            "extra",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Most-recently-seen inbound Meta message id, used for dedupe.
        # Meta retries delivery for ~7 days if a webhook ACK times out
        # or returns non-2xx, so dedupe by message id is mandatory.
        sa.Column("last_inbound_message_id", sa.String(128), nullable=True),
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
            "channel_id",
            "wa_id",
            name="uq_whatsapp_sessions_org_channel_wa",
        ),
    )
    op.create_index(
        "idx_whatsapp_sessions_workflow_run",
        "whatsapp_sessions",
        ["workflow_run_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_whatsapp_sessions_workflow_run", table_name="whatsapp_sessions")
    op.drop_table("whatsapp_sessions")
