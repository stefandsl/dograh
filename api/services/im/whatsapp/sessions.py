"""Per-conversation state for the WhatsApp channel.

One row per ``(organization_id, channel_id, wa_id)`` in
``whatsapp_sessions`` tracks the active workflow, current run, the
conversation state, and an ``extra`` JSON blob for misc context.

Mirrors ``telegram-bot/bot/sessions.py`` but lives inside the api
process and uses the project's async SQLAlchemy session factory.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

from api.db import db_client


async def get_or_create(
    *,
    organization_id: int,
    channel_id: int,
    wa_id: str,
) -> dict[str, Any]:
    """Look up the session row by (org, channel, wa_id) or create it."""
    async with db_client.async_session() as s:
        result = await s.execute(
            text(
                "SELECT id, workflow_id, workflow_run_id, state, extra, "
                "       last_inbound_message_id "
                "FROM whatsapp_sessions "
                "WHERE organization_id = :org "
                "  AND channel_id = :ch "
                "  AND wa_id = :wa"
            ),
            {"org": organization_id, "ch": channel_id, "wa": wa_id},
        )
        row = result.first()
        if row:
            return dict(row._mapping)
        result = await s.execute(
            text(
                "INSERT INTO whatsapp_sessions "
                "  (organization_id, channel_id, wa_id) "
                "VALUES (:org, :ch, :wa) "
                "RETURNING id, workflow_id, workflow_run_id, state, extra, "
                "          last_inbound_message_id"
            ),
            {"org": organization_id, "ch": channel_id, "wa": wa_id},
        )
        row = result.first()
        await s.commit()
        return dict(row._mapping) if row else {}


async def set_active_workflow(
    *,
    organization_id: int,
    channel_id: int,
    wa_id: str,
    workflow_id: Optional[int],
) -> None:
    """Set/replace the active workflow for the conversation.

    Resets ``workflow_run_id`` so the next inbound message opens a fresh
    run against the new workflow.
    """
    async with db_client.async_session() as s:
        await s.execute(
            text(
                "UPDATE whatsapp_sessions "
                "SET workflow_id = :wfid, workflow_run_id = NULL, "
                "    updated_at = now() "
                "WHERE organization_id = :org "
                "  AND channel_id = :ch "
                "  AND wa_id = :wa"
            ),
            {
                "wfid": workflow_id,
                "org": organization_id,
                "ch": channel_id,
                "wa": wa_id,
            },
        )
        await s.commit()


async def set_workflow_run(
    *,
    organization_id: int,
    channel_id: int,
    wa_id: str,
    workflow_run_id: int,
) -> None:
    """Pin the current workflow_run_id to the session."""
    async with db_client.async_session() as s:
        await s.execute(
            text(
                "UPDATE whatsapp_sessions "
                "SET workflow_run_id = :rid, updated_at = now() "
                "WHERE organization_id = :org "
                "  AND channel_id = :ch "
                "  AND wa_id = :wa"
            ),
            {
                "rid": workflow_run_id,
                "org": organization_id,
                "ch": channel_id,
                "wa": wa_id,
            },
        )
        await s.commit()


async def mark_inbound_seen(
    *,
    organization_id: int,
    channel_id: int,
    wa_id: str,
    message_id: str,
) -> bool:
    """Record the inbound message id, returning ``True`` if it's new.

    Used as the dedupe gate against Meta's at-least-once delivery. Returns
    ``False`` if the row's ``last_inbound_message_id`` already matched —
    the caller should ack the webhook and drop the message.
    """
    async with db_client.async_session() as s:
        result = await s.execute(
            text(
                "SELECT last_inbound_message_id FROM whatsapp_sessions "
                "WHERE organization_id = :org "
                "  AND channel_id = :ch "
                "  AND wa_id = :wa"
            ),
            {"org": organization_id, "ch": channel_id, "wa": wa_id},
        )
        row = result.first()
        if row and row._mapping["last_inbound_message_id"] == message_id:
            return False
        await s.execute(
            text(
                "UPDATE whatsapp_sessions "
                "SET last_inbound_message_id = :mid, updated_at = now() "
                "WHERE organization_id = :org "
                "  AND channel_id = :ch "
                "  AND wa_id = :wa"
            ),
            {
                "mid": message_id,
                "org": organization_id,
                "ch": channel_id,
                "wa": wa_id,
            },
        )
        await s.commit()
        return True
