from enum import Enum
from dataclasses import dataclass
import discord

class State(Enum):
    STARTING = 1
    PLAYING = 2
    VOTING = 3
    COMPLETE = 4

@dataclass
class Player:
    member: discord.Member
    count: int
    votes: list[int]
    reactions: list[list[str]]

@dataclass
class Team:
    team: discord.VoiceChannel
    players: list[Player]

class Game:
    guild: discord.Guild
    team1: Team
    team2: Team
    throwers: list[discord.Member]
    message: discord.Message
    state: State
    info: str