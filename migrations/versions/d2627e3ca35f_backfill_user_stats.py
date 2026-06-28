"""backfill_user_stats

Revision ID: d2627e3ca35f
Revises: 900a4977190a
Create Date: 2026-06-20 18:35:35.084907

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2627e3ca35f"
down_revision: Union[str, Sequence[str], None] = "900a4977190a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
        UPDATE users SET games_played = subq.cnt
        FROM (
            SELECT user_id, COUNT(*) AS cnt FROM game_players GROUP BY user_id
        ) subq
        WHERE users.user_id = subq.user_id
    """)
    )

    conn.execute(
        sa.text("""
        UPDATE users SET games_won = subq.cnt
        FROM (
            SELECT gp.user_id, COUNT(*) AS cnt
            FROM game_players gp
            JOIN games g ON gp.game_id = g.game_id
            WHERE g.winning_channel_id IS NOT NULL
              AND gp.channel_id = g.winning_channel_id
            GROUP BY gp.user_id
        ) subq
        WHERE users.user_id = subq.user_id
    """)
    )

    conn.execute(
        sa.text("""
        UPDATE users SET games_as_thrower = subq.cnt
        FROM (
            SELECT user_id, COUNT(*) AS cnt
            FROM game_players WHERE is_thrower = true GROUP BY user_id
        ) subq
        WHERE users.user_id = subq.user_id
    """)
    )

    conn.execute(
        sa.text("""
        UPDATE users SET games_thrown = subq.cnt
        FROM (
            SELECT gp.user_id, COUNT(*) AS cnt
            FROM game_players gp
            JOIN games g ON gp.game_id = g.game_id
            WHERE gp.is_thrower = true
              AND g.winning_channel_id IS NOT NULL
              AND gp.channel_id != g.winning_channel_id
            GROUP BY gp.user_id
        ) subq
        WHERE users.user_id = subq.user_id
    """)
    )

    conn.execute(
        sa.text("""
        UPDATE users SET total_votes_received = subq.cnt
        FROM (
            SELECT target_id AS user_id, COUNT(*) AS cnt FROM votes GROUP BY target_id
        ) subq
        WHERE users.user_id = subq.user_id
    """)
    )

    conn.execute(
        sa.text("""
        UPDATE users SET votes_received_as_thrower = subq.cnt
        FROM (
            SELECT v.target_id AS user_id, COUNT(*) AS cnt
            FROM votes v
            JOIN game_players gp ON v.game_id = gp.game_id AND v.target_id = gp.user_id
            WHERE gp.is_thrower = true
            GROUP BY v.target_id
        ) subq
        WHERE users.user_id = subq.user_id
    """)
    )

    conn.execute(
        sa.text("""
        UPDATE users SET total_votes_cast = subq.cnt
        FROM (
            SELECT voter_id AS user_id, COUNT(*) AS cnt FROM votes GROUP BY voter_id
        ) subq
        WHERE users.user_id = subq.user_id
    """)
    )

    conn.execute(
        sa.text("""
        UPDATE users SET votes_cast_on_thrower = subq.cnt
        FROM (
            SELECT v.voter_id AS user_id, COUNT(*) AS cnt
            FROM votes v
            JOIN game_players gp ON v.game_id = gp.game_id AND v.target_id = gp.user_id
            WHERE gp.is_thrower = true
            GROUP BY v.voter_id
        ) subq
        WHERE users.user_id = subq.user_id
    """)
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("""
        UPDATE users SET
            games_played = 0, games_won = 0, games_as_thrower = 0, games_thrown = 0,
            total_votes_received = 0, votes_received_as_thrower = 0,
            total_votes_cast = 0, votes_cast_on_thrower = 0
    """)
    )
