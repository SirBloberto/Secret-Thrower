"""add_games_evaded

Revision ID: f8a3c1b9e7d4
Revises: d2627e3ca35f
Create Date: 2026-06-20 23:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8a3c1b9e7d4"
down_revision: Union[str, Sequence[str], None] = "d2627e3ca35f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "games_evaded",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Games where user was the Thrower, team lost, and they were not the most accused player",
        ),
    )

    # Backfill: thrower, team lost, not the most-voted player on their team
    op.execute(sa.text("""
        WITH vote_counts AS (
            SELECT v.game_id, gp.channel_id, v.target_id, COUNT(*) AS cnt
            FROM votes v
            JOIN game_players gp ON v.game_id = gp.game_id AND v.target_id = gp.user_id
            GROUP BY v.game_id, gp.channel_id, v.target_id
        ),
        most_accused AS (
            SELECT DISTINCT ON (game_id, channel_id) game_id, channel_id, target_id AS accused_id
            FROM vote_counts
            ORDER BY game_id, channel_id, cnt DESC
        )
        UPDATE users SET games_evaded = subq.cnt
        FROM (
            SELECT gp.user_id, COUNT(*) AS cnt
            FROM game_players gp
            JOIN games g ON gp.game_id = g.game_id
            LEFT JOIN most_accused ma
                ON ma.game_id = gp.game_id AND ma.channel_id = gp.channel_id
            WHERE gp.is_thrower = true
              AND g.winning_channel_id IS NOT NULL
              AND gp.channel_id != g.winning_channel_id
              AND (ma.accused_id IS NULL OR ma.accused_id != gp.user_id)
            GROUP BY gp.user_id
        ) subq
        WHERE users.user_id = subq.user_id
    """))


def downgrade() -> None:
    op.drop_column("users", "games_evaded")
