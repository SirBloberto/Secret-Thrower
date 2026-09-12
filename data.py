from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum

import discord


class GameState(Enum):
    SETUP = 1
    PLAYING = 2
    VOTING = 3
    REVEAL = 4


@dataclass
class Player:
    member: discord.Member
    is_thrower: bool = False


@dataclass
class Team:
    channel: discord.VoiceChannel
    players: list[Player] = field(default_factory=list)


@dataclass
class GameSettings:
    thrower_info: bool = False
    voting_timer: int = 60


class Game:
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.game_id: int | None = None
        self.state = GameState.SETUP
        self.team1: Team | None = None
        self.team2: Team | None = None
        self.thrower_ids: list[int] = []
        self.winning_channel_id: int | None = None
        self.vote_end_timestamp: int | None = None
        self.host_id: int | None = None
        self.text_channel_id: int | None = None
        self.settings = GameSettings()
        self.message: discord.Message | None = None
        self.voting_task: asyncio.Task[None] | None = None

    def get_teams(self) -> list[Team | None]:
        return [self.team1, self.team2]

    def to_json(self) -> str:
        return json.dumps(
            {
                "game_id": self.game_id,
                "guild_id": self.guild_id,
                "state": self.state.value,
                "thrower_ids": self.thrower_ids,
                "winning_channel_id": self.winning_channel_id,
                "vote_end_timestamp": self.vote_end_timestamp,
                "host_id": self.host_id,
                "text_channel_id": self.text_channel_id,
                "message_id": self.message.id if self.message else None,
                "team1_channel_id": self.team1.channel.id if self.team1 else None,
                "team1_player_ids": [p.member.id for p in self.team1.players] if self.team1 else [],
                "team2_channel_id": self.team2.channel.id if self.team2 else None,
                "team2_player_ids": [p.member.id for p in self.team2.players] if self.team2 else [],
                "settings": {
                    "voting_timer": self.settings.voting_timer,
                    "thrower_info": self.settings.thrower_info,
                },
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> Game:
        """Restores bare game metadata from Redis. team1/team2/message must be
        re-attached from the Discord API before the object is usable."""
        data = json.loads(json_str)
        game = cls(guild_id=data["guild_id"])
        game.game_id = data["game_id"]
        game.state = GameState(data["state"])
        game.thrower_ids = data["thrower_ids"]
        game.winning_channel_id = data["winning_channel_id"]
        game.vote_end_timestamp = data.get("vote_end_timestamp")
        game.host_id = data.get("host_id")
        game.text_channel_id = data.get("text_channel_id")
        s = data["settings"]
        game.settings = GameSettings(voting_timer=s["voting_timer"], thrower_info=s["thrower_info"])
        return game
