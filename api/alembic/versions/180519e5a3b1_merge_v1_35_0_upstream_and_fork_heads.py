"""merge v1.35.0 upstream and fork heads

Revision ID: 180519e5a3b1
Revises: 91cc6ba3e1c7, c6d6e639d9f0
Create Date: 2026-06-18 10:58:38.356398

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '180519e5a3b1'
down_revision: Union[str, None] = ('91cc6ba3e1c7', 'c6d6e639d9f0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
