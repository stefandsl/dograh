"""add telegram IM channel tables

Per ADR-103: drop SQLite/FTS5 from the merged bot, use Postgres
``to_tsvector('simple') + GIN`` instead. Three tables:

- ``telegram_memory_facts`` — bot's "remember-this" vault (FTS over body)
- ``telegram_sessions`` — per-chat active workflow + state
- ``telegram_scheduled_tasks`` — APScheduler-style jobs persisted

All scoped to ``organizations.id`` per the existing multi-tenant pattern.

Revision ID: a4b5c6d7e8f9
Revises: 6bd9f67ec994
Create Date: 2026-05-27 22:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, None] = "6bd9f67ec994"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_memory_facts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "tags",
            sa.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Generated column carrying the tsvector. Indexed by GIN below.
        # ``simple`` config is deliberate (see ADR-103) — predictable for
        # mixed-language chats.
        sa.Column(
            "body_tsv",
            sa.dialects.postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('simple', coalesce(body, ''))",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_telegram_memory_facts_tsv",
        "telegram_memory_facts",
        ["body_tsv"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_telegram_memory_facts_chat",
        "telegram_memory_facts",
        ["organization_id", "chat_id"],
    )

    op.create_table(
        "telegram_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
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
            "organization_id", "chat_id", name="uq_telegram_sessions_org_chat"
        ),
    )

    op.create_table(
        "telegram_scheduled_tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        # cron expression (5-field) OR ISO timestamp for one-shot tasks
        sa.Column("schedule", sa.String(255), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_telegram_scheduled_tasks_active_next",
        "telegram_scheduled_tasks",
        ["next_run_at"],
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index(
        "idx_telegram_scheduled_tasks_active_next",
        table_name="telegram_scheduled_tasks",
    )
    op.drop_table("telegram_scheduled_tasks")
    op.drop_constraint(
        "uq_telegram_sessions_org_chat",
        "telegram_sessions",
        type_="unique",
    )
    op.drop_table("telegram_sessions")
    op.drop_index("idx_telegram_memory_facts_chat", table_name="telegram_memory_facts")
    op.drop_index("idx_telegram_memory_facts_tsv", table_name="telegram_memory_facts")
    op.drop_table("telegram_memory_facts")
