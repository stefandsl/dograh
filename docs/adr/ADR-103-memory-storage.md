# ADR-103 — Memory storage: SQLite/FTS5 → Postgres FTS

**Status:** Accepted
**Date:** 2026-05-27
**Context:** Phase 0. CliClaw's bot keeps a per-chat "memory vault" of
facts the user has asked it to remember, plus a session history.
Original stack: SQLite WAL with an FTS5 virtual table for full-text
search over both. Bellerophone runs Postgres (pgvector enabled). Standing up
SQLite alongside Postgres for one tiny feature is amateurish.

## Decision

**Migrate the memory vault and session/history tables to Postgres.
Full-text search via `to_tsvector` + GIN index.** No SQLite anywhere
in the merged bot.

## Schema

Two new tables, created via Alembic migration alongside the existing
api migrations:

```sql
CREATE TABLE telegram_memory_facts (
    id              BIGSERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    chat_id         BIGINT NOT NULL,         -- Telegram chat id
    body            TEXT NOT NULL,
    tags            TEXT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    body_tsv        TSVECTOR GENERATED ALWAYS AS
                       (to_tsvector('simple', coalesce(body, ''))) STORED
);
CREATE INDEX idx_telegram_memory_facts_tsv
    ON telegram_memory_facts USING GIN (body_tsv);
CREATE INDEX idx_telegram_memory_facts_chat
    ON telegram_memory_facts (organization_id, chat_id);

CREATE TABLE telegram_sessions (
    id              BIGSERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    chat_id         BIGINT NOT NULL,
    workflow_id     INTEGER REFERENCES workflows(id),
    workflow_run_id INTEGER REFERENCES workflow_runs(id),
    state           VARCHAR(32) NOT NULL DEFAULT 'idle',
    extra           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, chat_id)
);
```

`simple` text-search config is the safe default (no language stemming;
matches "Ciao" and "ciao" but not "ciaone" → "ciao"). The bot's memory
queries are short literal phrases — stemming would do more harm than
good across mixed-language chats.

## Why not language-specific config (`italian`, `english`)

The original `MESSAGENET_COUNTRY=IT` default suggests the deployment is
Italy-heavy, but Telegram chats are international. `simple` keeps the
behaviour predictable. We can switch to per-chat configurable later if
search quality complaints come in.

## Why not `pgvector` semantic search

Overkill for a "remember-this-fact" notebook. The user typed the fact
verbatim; they'll type a substring to recall it. Keyword search wins.
If the use case grows into RAG, pgvector is already in this Postgres —
trivial to add then.

## Implications

- Alembic migration `api/alembic/versions/<id>_telegram_memory_tables.py`
  created in Phase 2.
- `telegram-bot/bot/memory.py` (KEEP-ADAPT) rewrites the SQLite query
  layer to SQLAlchemy + asyncpg using the Bellerophone `db_client` pattern.
- The CliClaw `workspace/*.db` SQLite file is **not migrated** — this is
  a fresh start. If you have important facts from CliClaw, manually
  export and re-add.
- FTS5's "tokenize on word" maps to Postgres `simple` config with the
  default dictionary. Behaviour parity for short phrase queries; both
  ignore punctuation.

## Future

If the bot grows a "search-across-chats" admin feature, add a
`(organization_id) WHERE …` index variant. Out of scope for the merge.
