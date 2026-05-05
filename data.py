from enum import Enum
from dataclasses import dataclass
import discord


class GameState(Enum):
    SETUP = 1
    PLAYING = 2
    VOTING = 3
    COMPLETE = 4 #THink of a better name. THis is to show the winners and throwers


@dataclass
class Player:
    member: discord.Member
    count: int
    votes: list[int]
    reactions: list[list[str]] #Do we need all this. Probably?
    #Make a constructor


@dataclass
class Team:
    team: discord.VoiceChannel #Are we still going ahead with voice channels
    players: list[Player] #Dictionary..


@dataclass
class GameSettings:
    thrower_info: bool = false
    voting_timer: int = 60

class Game:
    guild: discord.Guild
    team1: Team
    team2: Team
    throwers: list[list[discord.Member]]
    message: discord.Message
    state: State
    settings: GameSettings

    def get_embed():
        return message.embed[0]
    
    def get_teams():
        return [team1, team2]