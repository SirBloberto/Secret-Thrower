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
                for member in game.throwers:
                    if player.member.id == member.member.id:
                        string += THROWER
                        break
            string += player.member.name
            if game.state == State.COMPLETE:
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

def player_to_reaction(game, id):
    teams = [game.team1, game.team2]
    for i, team in enumerate(teams):
        for j, player in enumerate(team.players):
            if player.member.id == id:
                return REACTIONS[i][j]
            
def reaction_to_player(game, reaction):
    teams = [game.team1, game.team2]
    for i, team in enumerate(teams):
        for j, player in enumerate(team.players):
            if REACTIONS[i][j] == reaction:
                return player