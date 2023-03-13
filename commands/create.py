import discord
import json
from bot import games, tree
from data import *
from utils import *

@tree.command(name="create",description="Create a secret thrower game")
@discord.app_commands.describe(team1="A voice channel containing members for a team")
@discord.app_commands.describe(team2="A voice channel containing members for a team")
@discord.app_commands.describe(info="Any additional info to be included")
async def create(interaction: discord.Interaction, team1: discord.VoiceChannel, team2: discord.VoiceChannel, info: str=None):
    global games
    global json
    guild = interaction.guild
    if get_game(games, guild) != None:
        return await interaction.response.send_message("Already in a game", ephemeral=True, delete_after=60.0)
    if team1 == team2:
        return await interaction.response.send_message("Voice channels must be different", ephemeral=True, delete_after=60.0)
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    if str(guild.id) not in config:
        config[str(guild.id)] = 60
        with open('config.json', 'w') as config_out:
            json.dump(config, config_out, indent=4)
    game = Game()
    game.guild = guild
    game.team1 = Team(team1, [Player(member, 0, [None, None], [[],[]]) for member in team1.members])
    game.team2 = Team(team2, [Player(member, 0, [None, None], [[],[]]) for member in team2.members])
    game.throwers = []
    game.state = State.STARTING
    game.info = info
    embed = discord.Embed(title="Secret Thrower", description=info)
    team1_players, team2_players = list_players(game)
    embed.add_field(name=team1, value=team1_players)
    embed.add_field(name=team2, value=team2_players)
    await interaction.response.send_message("Game starting", ephemeral=True, delete_after=0.0)
    game.message = await interaction.channel.send(embed=embed)
    games.append(game)