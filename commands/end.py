import asyncio
import discord
import json
import time
from bot import games, tree
from constants import *
from data import *
from utils import *

@tree.command(name="end", description="End the secret thrower game and assign a winner")
@discord.app_commands.describe(winner="Which team won the game")
async def end(interaction: discord.Interaction, winner: discord.VoiceChannel):
    global games
    global asyncio
    global json
    global time
    guild = interaction.guild
    game = get_game(games, guild)
    if game == None:
        return await interaction.response.send_message("Not in a game! Use /create to start a Secret-Thrower game", ephemeral=True, delete_after=60.0)
    if game.state != State.PLAYING:
        #Handle which state we are in and give suggestion
        return await interaction.response.send_message(game_state(game.state, State.PLAYING), ephemeral=True, delete_after=60.0)
    if winner.id != game.team1.team.id and winner.id != game.team2.team.id:
        return await interaction.response.send_message(f"Team not found.  Options are {game.team1.team.name} and {game.team2.team.name}", ephemeral=True, delete_after=60.0)
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    game.state = State.VOTING
    embed = game.message.embeds[0]
    end_time = time.time() + config[str(guild.id)]
    embed.description = "Voting ends <t:" + str(int(end_time)) + ":R>" + (" : " + game.info if game.info != None else "")
    team1_players, team2_players = list_players(game)
    team1_name, team2_name = game.team1.team.name, game.team2.team.name
    if winner.id == game.team1.team.id:
        team1_name = WINNER + " " + team1_name
    if winner.id == game.team2.team.id:
        team2_name = WINNER + " " + team2_name
    embed.set_field_at(0, name=team1_name, value=team1_players)
    embed.set_field_at(1, name=team2_name, value=team2_players)
    game.message = await game.message.edit(embed=embed)
    await interaction.response.send_message(f"Winner is {winner}! Vote for a secret thrower on each team!", delete_after=60.0)
    for index in range(0, len(game.team1.players)):
        await game.message.add_reaction(REACTIONS[0][index])
    await game.message.add_reaction(VS)
    for index in range(0, len(game.team2.players)):
        await game.message.add_reaction(REACTIONS[1][index])
    await asyncio.sleep(end_time - time.time())
    await game.message.clear_reactions()
    teams = [game.team1, game.team2]
    for i, team in enumerate(teams):
        for player in team.players:
            vote = player_to_reaction(game, player.votes[i])
            for emoji in player.reactions[i]:
                if emoji != vote:
                    reaction_to_player(game, emoji).count -= 1
    embed = game.message.embeds[0]
    embed.description = game.info if game.info != None else ""
    team1_players, team2_players = list_players(game)
    embed.set_field_at(0, name=embed.fields[0].name, value=team1_players)
    embed.set_field_at(1, name=embed.fields[1].name, value=team2_players)
    game.message = await game.message.edit(embed=embed)
    for index in range(0, len(games)):
        if games[index].guild.id == guild.id:
            del games[index]
            break