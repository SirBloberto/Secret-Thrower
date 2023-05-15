import discord
import random
import json
from bot import games, tree
from data import *
from utils import *

@tree.command(name="send", description='Assign the secret throwers for a game')
@discord.app_commands.describe(team1_count="Number of secret throwers on team1")
@discord.app_commands.describe(team2_count="Number of secret throwers on team2")
async def send(interaction: discord.Interaction, team1_count: int = 1, team2_count: int = 1):
    global games
    global random
    guild = interaction.guild
    game = get_game(games, guild)
    if game == None:
        return await interaction.response.send_message("Not in a game! Use /create to start a Secret-Thrower game", ephemeral=True, delete_after=60.0)
    if game.state != State.STARTING:
        return await interaction.response.send_message(game_state(game.state, State.STARTING), ephemeral=True, delete_after=60.0)
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    thrower_info = config[str(guild.id)]['thrower_info']
    team1_throwers=random.sample(game.team1.players, len(game.team1.players) if len(game.team1.players) < team1_count else team1_count)
    team2_throwers=random.sample(game.team2.players, len(game.team2.players) if len(game.team2.players) < team2_count else team2_count)
    game.throwers[0]=team1_throwers
    game.throwers[1]=team2_throwers
    for index in range(game.teams):
        for player in game.throwers[index]:
            message="You are the secret thrower! Your goal is to lose the game without being discovered by others. "
            if thrower_info:
                team_throwers=[thrower for thrower in game.throwers[index] if thrower != player]
                if len(team_throwers) == 0:
                    message+="You are alone."
                elif len(team_throwers) == 1:
                    message+="Your partner is: " + team_throwers[0].member.name
                elif len(team_throwers) >= 2:
                    message+="Your partners are: " + "".join(str(thrower.member.name) for thrower in team_throwers)
            await player.member.send(message)
    game.state = State.PLAYING
    await interaction.response.send_message(f"Secret Thrower count -> Team1: {team1_count}, Team2: {team2_count}", ephemeral=not thrower_info, delete_after=60.0)
    await interaction.channel.send("Secret Throwers have been assigned", delete_after=60.0)