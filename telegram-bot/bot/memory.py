"""Bot memory vault — Postgres FTS-backed fact store.

Per ADR-103: ``telegram_memory_facts`` with a generated tsvector column
and a GIN index. Three public functions: add, search, list.

Phase 2 ships these helpers + a unit-test surface; Phase 5 wires the
``/remember`` / ``/memory`` handlers.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from .db import session_factory


async def add_fact(
    *, organization_id: int, chat_id: int, body: str, tags: list[str] | None = None
) -> int:
    """Insert a fact, returns the new row id."""
    Session = session_factory()
    async with Session() as s:
        result = await s.execute(
            text(
                "INSERT INTO telegram_memory_facts "
                "(organization_id, chat_id, body, tags) "
                "VALUES (:org, :chat, :body, :tags) "
                "RETURNING id"
            ),
            {
                "org": organization_id,
                "chat": chat_id,
                "body": body,
                "tags": tags or [],
            },
        )
        row = result.first()
        await s.commit()
        return int(row[0]) if row else 0


async def search_facts(
    *, organization_id: int, chat_id: int, query: str, limit: int = 10
) -> list[dict[str, Any]]:
    """Full-text search over a chat's vault. Empty query → recent facts."""
    Session = session_factory()
    async with Session() as s:
        if query.strip():
            result = await s.execute(
                text(
                    "SELECT id, body, tags, created_at "
                    "FROM telegram_memory_facts "
                    "WHERE organization_id = :org "
                    "  AND chat_id = :chat "
                    "  AND body_tsv @@ plainto_tsquery('simple', :q) "
                    "ORDER BY created_at DESC "
                    "LIMIT :limit"
                ),
                {"org": organization_id, "chat": chat_id, "q": query, "limit": limit},
            )
        else:
            result = await s.execute(
                text(
                    "SELECT id, body, tags, created_at "
                    "FROM telegram_memory_facts "
                    "WHERE organization_id = :org AND chat_id = :chat "
                    "ORDER BY created_at DESC "
                    "LIMIT :limit"
                ),
                {"org": organization_id, "chat": chat_id, "limit": limit},
            )
        return [dict(row._mapping) for row in result.all()]


async def delete_fact(*, organization_id: int, chat_id: int, fact_id: int) -> bool:
    """Hard delete; returns True if a row was removed."""
    Session = session_factory()
    async with Session() as s:
        result = await s.execute(
            text(
                "DELETE FROM telegram_memory_facts "
                "WHERE id = :id AND organization_id = :org AND chat_id = :chat"
            ),
            {"id": fact_id, "org": organization_id, "chat": chat_id},
        )
        await s.commit()
        return (result.rowcount or 0) > 0
