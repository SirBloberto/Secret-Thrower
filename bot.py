import asyncio
import discord
import json
import os
import random
import time
from data import *
from dotenv import dotenv_values
from utils import *

ENV = dotenv_values(".env")

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
intents.members = True
intents.reactions = True
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

games = []

@tree.command(name="create",description="Create a secret thrower game")
@discord.app_commands.describe(team1="A voice channel containing members for a team")
@discord.app_commands.describe(team2="A voice channel containing members for a team")
@discord.app_commands.describe(info="Any additional info to be included")
async def create(interaction: discord.Interaction, team1: discord.VoiceChannel, team2: discord.VoiceChannel, info: str=None):
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

@tree.command(name="send", description='Assign the secret throwers for a game')
@discord.app_commands.describe(team1_count="Number of secret throwers on team1")
@discord.app_commands.describe(team2_count="Number of secret throwers on team2")
async def send(interaction: discord.Interaction, team1_count: int = 1, team2_count: int = 1):
    guild = interaction.guild
    game = get_game(games, guild)
    if game == None:
        return await interaction.response.send_message("Not in a game!", ephemeral=True, delete_after=60.0)
    if game.state != State.STARTING:
        return await interaction.response.send_message("Game not in correct state", ephemeral=True, delete_after=60.0)
    game.throwers.extend(random.sample(game.team1.players, len(game.team1.players) if len(game.team1.players) < team1_count else team1_count))
    game.throwers.extend(random.sample(game.team2.players, len(game.team2.players) if len(game.team2.players) < team2_count else team2_count))
    for player in game.throwers:
        await player.member.send("You are the secret thrower! Your goal is to lose the game without being discovered by others", delete_after=60.0)
    game.state = State.PLAYING
    await interaction.response.send_message(f"Secret Thrower count: {team1_count} {team2_count}", ephemeral=True, delete_after=60.0)
    await interaction.channel.send("Secret Throwers have been assigned", delete_after=60.0)

@tree.command(name="end", description="End the secret thrower game and assign a winner")
@discord.app_commands.describe(winner="Which team won the game")
async def end(interaction: discord.Interaction, winner: discord.VoiceChannel):
    guild = interaction.guild
    game = get_game(games, guild)
    if game == None:
        return await interaction.response.send_message("Not in a game!", ephemeral=True, delete_after=60.0)
    if game.state != State.PLAYING:
        return await interaction.response.send_message("Game not in correct state", ephemeral=True, delete_after=60.0)
    if winner.id != game.team1.team.id and winner.id != game.team2.team.id:
        return await interaction.response.send_message("Team not found", ephemeral=True, delete_after=60.0)
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    game.state = State.VOTING
    embed = game.message.embeds[0]
    end_time = time.time() + config[str(guild.id)]
    embed.description = "Voting ends <t:" + str(int(end_time)) + ":R>" + (" : " + game.info if game.info != None else "")
    team1_players, team2_players = list_players(game)
    team1_name, team2_name = game.team1.team.name, game.team2.team.name
    if winner.id == game.team1.team.id:
        team1_name += " " + WINNER
    if winner.id == game.team2.team.id:
        team2_name += " " + WINNER
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
    game.state = State.COMPLETE
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

@tree.command(name="add", description="Add a player to a secret thrower team")
@discord.app_commands.describe(team="The team to add the player")
@discord.app_commands.describe(user="The player to be added to the secret thrower game")
async def add(interaction: discord.Interaction, team: discord.VoiceChannel, user: discord.Member):
    guild = interaction.guild
    game = get_game(games, guild)
    if game == None:
        return await interaction.response.send_message("Not in a game!", ephemeral=True, delete_after=60.0)
    if game.state != State.STARTING:
        return await interaction.response.send_message("Game not in correct state", ephemeral=True, delete_after=60.0)
    if team.id != game.team1.team.id and team.id != game.team2.team.id:
        return await interaction.response.send_message("Could not find team", ephemeral=True, delete_after=60.0)
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

@tree.command(name="remove", description="Remove a player from a secret thrower game")
@discord.app_commands.describe(user="The player to be removed from the secret thrower game")
async def add(interaction: discord.Interaction, user: discord.Member):
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

@tree.command(name="timer", description="Set the current secret-thrower voting timer OR show current timer")
@discord.app_commands.describe(length="The length of time in seconds for voting")
async def timer(interaction: discord.Interaction, length: int=0):
    guild = str(interaction.guild.id)
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    if guild not in config:
        config[guild] = 60
    if length == 0:
        await interaction.response.send_message(f"Current secret thrower voting timer is {config[guild]} seconds", ephemeral=True, delete_after=60.0)
    config[guild] = length
    with open('config.json', 'w') as config_out:
        json.dump(config, config_out, indent=4)
    await interaction.response.send_message(f"Changed the secret thrower voting timer to {length} seconds", ephemeral=True, delete_after=60.0)

@client.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.user):
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
            if REACTIONS[i][j][0] == reaction.emoji:
                player.count += 1
                member.votes[i] = player.member.id
                for emoji in member.reactions[i][:]:
                    if emoji != reaction.emoji:
                        await reaction.message.remove_reaction(emoji, user)
                break

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

@client.event
async def on_ready():
    await tree.sync()
    if not os.path.exists("config.json"):
        with open("config.json", "w") as config:
            json.dump({}, config)
    print(f"{client.user} Ready!")

client.run(ENV["TOKEN"])