from data import *
from constants import *

def list_players(game: Game):
    teams = [game.team1, game.team2]
    output = []
    for i, team in enumerate(teams):
        string = ""
        for j, player in enumerate(team.players):
            if game.state == State.VOTING:
                string += EMOJIS[i][j]
            if game.state == State.COMPLETE:
                for member in game.throwers[i]:
                    if player.member.id == member.id:
                        string += THROWER
            string += player.member.name
            if game.state == State.VOTING or game.state == State.COMPLETE:
                string += " : " + str(player.count)
            string += "\n"
        output.append(string)
    return output[0], output[1]

def get_game(games, guild):
    for game in games:
        if game.guild.id == guild.id:
            return game
    return None

def has_player(game, user):
    for player in game.team1.players:
        if player.member.id == user.id:
            return True
    for player in game.team2.players:
        if player.member.id == user.id:
            return True
    return False