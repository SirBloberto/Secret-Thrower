from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    """Stores persistent player profiles and identity data."""

    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, comment="The unique Discord Snowflake ID for the user"
    )
    username: Mapped[str] = mapped_column(
        String(32), comment="The Discord username of the player at the time of last record"
    )

    games_played: Mapped[int] = mapped_column(Integer, default=0, server_default="0", comment="Total matches completed")
    games_won: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="Total matches won regardless of role"
    )
    games_as_thrower: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="How many times this user was assigned the Secret Thrower role"
    )
    games_thrown: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        comment="Games where user was the Thrower and their team lost (successful bluff)",
    )
    total_votes_received: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="Total votes cast against this user by others"
    )
    votes_received_as_thrower: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        comment="Votes received while user was actually the thrower (Caught count)",
    )
    total_votes_cast: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="Total number of votes this user has sent"
    )
    votes_cast_on_thrower: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        comment="How many times this user correctly voted for the actual thrower",
    )
    games_evaded: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        comment="Games where user was the Thrower, team lost, and they were not the most accused player",
    )

    innocent_elo: Mapped[float] = mapped_column(Float, default=50.0, server_default="50.0")
    thrower_elo: Mapped[float] = mapped_column(Float, default=50.0, server_default="50.0")
    win_streak: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="Current consecutive win streak"
    )
    best_win_streak: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="All-time best consecutive win streak"
    )

    game_history: Mapped[List["Player"]] = relationship(back_populates="user")
    votes_received: Mapped[List["Vote"]] = relationship(foreign_keys="[Vote.target_id]", back_populates="target")
    votes_cast: Mapped[List["Vote"]] = relationship(foreign_keys="[Vote.voter_id]", back_populates="voter")


class Game(Base):
    """Stores the configuration and final results of a Secret-Thrower session."""

    __tablename__ = "games"

    game_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, comment="The Discord Message ID of the game embed"
    )
    guild_id: Mapped[int] = mapped_column(
        BigInteger, index=True, comment="The Discord Snowflake ID of the server where the game was played"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Timestamp when the game result was committed to the database",
    )
    winning_channel_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, comment="The ID of the voice channel/team that won the game"
    )

    players: Mapped[List["Player"]] = relationship(back_populates="game")
    votes: Mapped[List["Vote"]] = relationship(back_populates="game")


class Player(Base):
    """Maps users to games and records their specific role and team."""

    __tablename__ = "game_players"

    game_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("games.game_id"), primary_key=True, comment="Reference to the game session"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id"), primary_key=True, index=True, comment="Reference to the user"
    )
    channel_id: Mapped[int] = mapped_column(
        BigInteger, index=True, comment="The ID of the voice channel this player was assigned to"
    )
    is_thrower: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="Whether the player was secretly assigned to lose the game"
    )

    game: Mapped["Game"] = relationship(back_populates="players")
    user: Mapped["User"] = relationship(back_populates="game_history")


class Vote(Base):
    """Records the accusations made by players during the voting phase."""

    __tablename__ = "votes"

    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.game_id"),
        primary_key=True,
        comment="Reference to the game session where the vote occurred",
    )
    voter_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id"), primary_key=True, comment="The ID of the player who cast the vote"
    )
    target_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id"), primary_key=True, comment="The ID of the player being accused"
    )

    game: Mapped["Game"] = relationship(back_populates="votes")
    target: Mapped["User"] = relationship(foreign_keys=[target_id], back_populates="votes_received")
    voter: Mapped["User"] = relationship(foreign_keys=[voter_id], back_populates="votes_cast")
