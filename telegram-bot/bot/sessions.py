"""Per-chat active workflow state.

Phase 2 reads + writes ``telegram_sessions`` rows. The active workflow
(`workflow_id`) is what `/workflows pick <id>` sets and what the text
message handler dispatches into. `workflow_run_id` is set lazily when
the next text message lands and we open a manual run for it.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

from .db import session_factory


async def get_or_create(*, organization_id: int, chat_id: int) -> dict[str, Any]:
    Session = session_factory()
    async with Session() as s:
        result = await s.execute(
            text(
                "SELECT id, workflow_id, workflow_run_id, state, extra "
                "FROM telegram_sessions "
                "WHERE organization_id = :org AND chat_id = :chat"
            ),
            {"org": organization_id, "chat": chat_id},
        )
        row = result.first()
        if row:
            return dict(row._mapping)
        result = await s.execute(
            text(
                "INSERT INTO telegram_sessions (organization_id, chat_id) "
                "VALUES (:org, :chat) "
                "RETURNING id, workflow_id, workflow_run_id, state, extra"
            ),
            {"org": organization_id, "chat": chat_id},
        )
        row = result.first()
        await s.commit()
        return dict(row._mapping) if row else {}


async def set_active_workflow(
    *, organization_id: int, chat_id: int, workflow_id: Optional[int]
) -> None:
    Session = session_factory()
    async with Session() as s:
        await s.execute(
            text(
                "UPDATE telegram_sessions "
                "SET workflow_id = :wfid, workflow_run_id = NULL, "
                "    updated_at = now() "
                "WHERE organization_id = :org AND chat_id = :chat"
            ),
            {"wfid": workflow_id, "org": organization_id, "chat": chat_id},
        )
        await s.commit()


async def set_active_run(
    *, organization_id: int, chat_id: int, workflow_run_id: int
) -> None:
    Session = session_factory()
    async with Session() as s:
        await s.execute(
            text(
                "UPDATE telegram_sessions "
                "SET workflow_run_id = :run, state = 'running', updated_at = now() "
                "WHERE organization_id = :org AND chat_id = :chat"
            ),
            {"run": workflow_run_id, "org": organization_id, "chat": chat_id},
        )
        await s.commit()
