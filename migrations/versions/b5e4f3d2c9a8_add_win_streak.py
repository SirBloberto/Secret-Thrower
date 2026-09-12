"""add_win_streak

Revision ID: b5e4f3d2c9a8
Revises: a3f2e1d9c8b7
Create Date: 2026-06-21 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b5e4f3d2c9a8"
down_revision: Union[str, Sequence[str], None] = "a3f2e1d9c8b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "win_streak", sa.Integer(), server_default="0", nullable=False, comment="Current consecutive win streak"
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "best_win_streak",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="All-time best consecutive win streak",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "win_streak")
    op.drop_column("users", "best_win_streak")
