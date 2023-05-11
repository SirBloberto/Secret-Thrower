import discord
from bot import client, games
from constants import *
from utils import *

@client.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.user):
    global games
    guild = reaction.message.guild
    game = get_game(games, guild)
    if game == None:
        return
    if reaction.message != game.message:
        return
    if game.state != State.VOTING:
        return
    if not has_player(game, user):
        return
    teams = [game.team1, game.team2]
    member = None
    for team in teams:
        for player in team.players:
            if player.member.id == user.id:
                member = player
                break
    for i, team in enumerate(teams):
        if reaction.emoji not in REACTIONS[i]:
            continue
        member.reactions[i].append(reaction.emoji)
        for j, player in enumerate(team.players):
            if REACTIONS[i][j] == reaction.emoji:
                player.count += 1
                member.votes[i] = player.member.id
                for emoji in member.reactions[i][:]:
                    if emoji != reaction.emoji:
                        await reaction.message.remove_reaction(emoji, user)
                break