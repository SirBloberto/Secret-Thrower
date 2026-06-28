"""add_achievements

Revision ID: a3f2e1d9c8b7
Revises: c1e4f5a9b8d2
Create Date: 2026-06-21 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f2e1d9c8b7"
down_revision: Union[str, Sequence[str], None] = "c1e4f5a9b8d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "achievements",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
            comment="Bitmask of unlocked achievements",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "achievements")
