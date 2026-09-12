"""drop_paid_feature_schema

Revision ID: e7d1c4a2b930
Revises: b5e4f3d2c9a8
Create Date: 2026-09-12 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7d1c4a2b930"
down_revision: Union[str, Sequence[str], None] = "b5e4f3d2c9a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "achievements")

    op.drop_index("ix_guild_elo_roles_guild_id", table_name="guild_elo_roles")
    op.drop_table("guild_elo_roles")

    op.drop_table("guild_settings")

    op.drop_index(op.f("ix_subscriptions_target_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
    sa.Enum(name="subscriptiontype").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False, comment="Internal primary key for the subscription record"),
        sa.Column(
            "target_id",
            sa.BigInteger(),
            nullable=False,
            comment="The Discord User ID or Guild ID that owns this subscription",
        ),
        sa.Column(
            "type",
            sa.Enum("USER", "GUILD", name="subscriptiontype"),
            nullable=False,
            comment="Defines if the subscription applies to a single user or an entire server",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="Quick-check flag to see if the subscription is currently valid",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="The exact timestamp when premium access should be revoked",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_subscriptions_target_id"), "subscriptions", ["target_id"], unique=True)

    op.create_table(
        "guild_settings",
        sa.Column("guild_id", sa.BigInteger(), nullable=False, comment="The Discord Snowflake ID of the server"),
        sa.Column(
            "voting_timer",
            sa.Integer(),
            server_default="60",
            nullable=False,
            comment="Voting phase duration in seconds",
        ),
        sa.Column(
            "thrower_info",
            sa.Boolean(),
            server_default="false",
            nullable=False,
            comment="Whether throwers are told about teammates who are also throwers",
        ),
        sa.PrimaryKeyConstraint("guild_id"),
    )

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
