import discord
from bot import games, tree
from data import *
from utils import *

@tree.command(name="remove", description="Remove a player from a secret thrower game")
@discord.app_commands.describe(user="The player to be removed from the secret thrower game")
async def add(interaction: discord.Interaction, user: discord.Member):
    global games
    guild = interaction.guild
    game = get_game(games, guild)
    if game == None:
        return await interaction.response.send_message("Not in a game!", ephemeral=True, delete_after=60.0)
    if game.state != State.STARTING:
        return await interaction.response.send_message("Game not in correct state", ephemeral=True, delete_after=60.0)
    teams = [game.team1, game.team2]
    for team in teams:
        for player in team.players:
            if player.member.id == user.id:
                team.players.remove(player)
                embed = game.message.embeds[0]
                embed.description = game.info if game.info != None else ""
                team1_players, team2_players = list_players(game)
                embed.set_field_at(0, name=embed.fields[0].name, value=team1_players)
                embed.set_field_at(1, name=embed.fields[1].name, value=team2_players)
                game.message = await game.message.edit(embed=embed)
                return await interaction.response.send_message(f"Removed: {user.name}", ephemeral=True, delete_after=60.0)
    return await interaction.response.send_message(f"Game does not have player: {user.name}", ephemeral=True, delete_after=60.0)