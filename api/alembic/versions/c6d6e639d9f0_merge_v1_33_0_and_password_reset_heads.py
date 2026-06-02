"""merge v1.33.0 and password-reset heads

Unifies the two Alembic heads that result from merging upstream dograh-hq/main
(v1.33.0) into the fork:

- ``384be6596b36`` (upstream: make users.email case-insensitive)
- ``d8f9a0b1c2d3`` (fork: password_reset_tokens table)

No schema operations — this is a no-op merge point so ``alembic upgrade head``
resolves to a single head again.

Revision ID: c6d6e639d9f0
Revises: 384be6596b36, d8f9a0b1c2d3
Create Date: 2026-06-02 12:18:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "c6d6e639d9f0"
down_revision: Union[str, Sequence[str], None] = ("384be6596b36", "d8f9a0b1c2d3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
