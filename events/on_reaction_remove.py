import discord
from bot import client, games
from constants import *
from utils import *

@client.event
async def on_reaction_remove(reaction: discord.Reaction, user: discord.User):
    guild = reaction.message.guild
    game = get_game(games, guild)
    if game == None:
        return
    if reaction.message != game.message:
        pass
    if game.state != State.VOTING:
        pass
    if not has_player(game, user):
        return
    teams = [game.team1, game.team2]
    member = None
    for team in teams:
        for player in team.players:
            if player.member.id == user.id:
                member = player
    for i, team in enumerate(teams):
        if reaction.emoji not in REACTIONS[i]:
            continue
        member.reactions[i].remove(reaction.emoji)
        for j, player in enumerate(team.players):
            if REACTIONS[i][j][0] == reaction.emoji:
                player.count -= 1
                if len(member.reactions[i]) == 0:
                    member.votes[i] = None
                break