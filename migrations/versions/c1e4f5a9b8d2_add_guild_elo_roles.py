"""add_guild_elo_roles

Revision ID: c1e4f5a9b8d2
Revises: f8a3c1b9e7d4
Create Date: 2026-06-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1e4f5a9b8d2"
down_revision: Union[str, Sequence[str], None] = "f8a3c1b9e7d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "guild_elo_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("elo_type", sa.String(16), nullable=False),
        sa.Column("min_elo", sa.Float(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "role_id", name="uq_guild_elo_role"),
    )
    op.create_index("ix_guild_elo_roles_guild_id", "guild_elo_roles", ["guild_id"])


def downgrade() -> None:
    op.drop_index("ix_guild_elo_roles_guild_id", table_name="guild_elo_roles")
    op.drop_table("guild_elo_roles")
