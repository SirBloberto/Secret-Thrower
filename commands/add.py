import discord
from bot import games, tree
from data import *
from utils import *

@tree.command(name="add", description="Add/Move a user to a secret thrower team")
@discord.app_commands.describe(team="The team to add the user")
@discord.app_commands.describe(user="The user to be added to the secret thrower game")
async def add(interaction: discord.Interaction, team: discord.VoiceChannel, user: discord.Member):
    global games
    guild = interaction.guild
    game = get_game(games, guild)
    if game == None:
        return await interaction.response.send_message("Not in a game! Use /create to start a Secret-Thrower game", ephemeral=True, delete_after=60.0)
    if game.state != State.STARTING:
        return await interaction.response.send_message(game_state(game.state, State.STARTING), ephemeral=True, delete_after=60.0)
    if team.id != game.team1.team.id and team.id != game.team2.team.id:
        return await interaction.response.send_message(f"Team not found.  Options are {game.team1.team.name} and {game.team2.team.name}", ephemeral=True, delete_after=60.0)
    teams = [game.team1, game.team2]
    for game_team in teams:
        for player in game_team.players:
            if player.member.id == user.id:
                game_team.players.remove(player)
    for game_team in teams:
        if game_team.team.id != team.id:
            continue
        game_team.players.append(Player(user, 0, [None, None], [[],[]]))
    embed = game.message.embeds[0]
    embed.description = game.info if game.info != None else ""
    team1_players, team2_players = list_players(game)
    embed.set_field_at(0, name=embed.fields[0].name, value=team1_players)
    embed.set_field_at(1, name=embed.fields[1].name, value=team2_players)
    game.message = await game.message.edit(embed=embed)
    return await interaction.response.send_message(f"Added: {user.name} to {team.name}", ephemeral=True, delete_after=60.0)