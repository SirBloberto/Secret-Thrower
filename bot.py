import discord
import json
import random
import os
import time
import asyncio
from data import *
from dotenv import dotenv_values
from utils import *
from typing import List

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
    #if len(team1.members) == 0 or len(team2.members) == 0:
       #return await interaction.response.send_message("Voice channels cannot be empty", ephemeral=True, delete_after=60.0)
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    if str(guild.id) not in config:
        config[str(guild.id)] = Config(60, []).__dict__
        with open('config.json', 'w') as config_out:
            json.dump(config, config_out, indent=4)
    game = Game()
    game.guild = guild
    game.team1 = Team(team1, [Player(member, 0, [None, None]) for member in team1.members if member.id not in config[str(guild.id)]["blacklist"]])
    game.team2 = Team(team2, [Player(member, 0, [None, None]) for member in team2.members if member.id not in config[str(guild.id)]["blacklist"]])
    game.throwers = []
    game.state = State.STARTING
    game.info = info
    embed = discord.Embed(title="Secret Thrower", description=info)
    team1_string, team2_string = list_players(game)
    embed.add_field(name=team1, value=team1_string)
    embed.add_field(name=team2, value=team2_string)
    await interaction.response.send_message(embed=embed)
    game.message = await interaction.original_response()
    games.append(game)

#Can currently create same secret thrower multiple times
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
    game.throwers.extend(random.choices(game.team1.players, k=len(game.team1.players) if len(game.team1.players) < team1_count else team1_count))
    game.throwers.extend(random.choices(game.team2.players, k=len(game.team2.players) if len(game.team2.players) < team2_count else team2_count))
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
    embed.description = "Voting ends <t:" + str(int(time.time() + config[str(guild.id)]["timer"] + 1)) + ":R>" + (" : " + game.info if game.info != None else "")
    team1_string, team2_string = list_players(game)
    team1_name, team2_name = game.team1.team.name, game.team2.team.name
    if winner.id == game.team1.team.id:
        team1_name += " " + WINNER
    if winner.id == game.team2.team.id:
        team2_name += " " + WINNER
    embed.set_field_at(0, name=team1_name, value=team1_string)
    embed.set_field_at(1, name=team2_name, value=team2_string)
    game.message = await game.message.edit(embed=embed)
    await interaction.response.send_message(f"Winner is {winner}! Vote for a secret thrower on each team!", delete_after=60.0)
    for index in range(0, len(game.team1.players)):
        await game.message.add_reaction(REACTIONS[0][index])
    await game.message.add_reaction(VS)
    for index in range(0, len(game.team2.players)):
        await game.message.add_reaction(REACTIONS[1][index])
    await asyncio.sleep(config[str(guild.id)]["timer"])
    game.state = State.COMPLETE
    embed = game.message.embeds[0]
    embed.description = game.info if game.info != None else ""
    team1_string, team2_string = list_players(game)
    embed.set_field_at(0, name=embed.fields[0].name, value=team1_string)
    embed.set_field_at(1, name=embed.fields[1].name, value=team2_string)
    game.message = await game.message.edit(embed=embed)
    await game.message.clear_reactions()
    for index in range(0, len(games)):
        if games[index].guild.id == guild.id:
            del games[index]
            break

@tree.command(name="blacklist", description="Remove a member from participating in secret thrower games")
@discord.app_commands.describe(member="The member to blacklist")
async def blacklist(interaction: discord.Interaction, member: discord.Member):
    guild = str(interaction.guild.id)
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    if guild not in config:
        config[guild] = Config(60, []).__dict__
    if member.id in config[guild]['blacklist']:
        return await interaction.response.send_message(f"Already blacklisted: {member}", ephemeral=True, delete_after=60.0)
    config[guild]['blacklist'].append(member.id)
    with open('config.json', 'w') as config_out:
        json.dump(config, config_out, indent=4)
    await interaction.response.send_message(f"Blacklisted: {member}", delete_after=60.0)

@tree.command(name="whitelist", description="Remove a member from the secret thrower game blacklist")
@discord.app_commands.describe(member="The member to whitelist")
async def whitelist(interaction: discord.Interaction, member: discord.Member):
    guild = str(interaction.guild.id)
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    if guild not in config:
        config[guild] = Config(60, []).__dict__
    if member.id not in config[guild]['blacklist']:
        return await interaction.response.send_message(f"Already Whitelisted {member}", ephemeral=True, delete_after=60.0)
    config[guild]['blacklist'].remove(member.id)
    with open('config.json', 'w') as config_out:
        json.dump(config, config_out, indent=4)
    await interaction.response.send_message(f"Whitelisted: {member}", delete_after=60.0)

@tree.command(name="timer", description="Set the current secret-thrower voting timer")
@discord.app_commands.describe(length="The length of time in seconds for voting")
async def timer(interaction: discord.Interaction, length: int):
    guild = str(interaction.guild.id)
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    if guild not in config:
        config[guild] = Config(length, []).__dict__
    else:
        config[guild]["timer"] = length
    with open('config.json', 'w') as config_out:
        json.dump(config, config_out, indent=4)
    await interaction.response.send_message(f"Changed the secret thrower voting timer to {length} seconds", delete_after=60.0)

@tree.command(name="show", description="Show the currrent config setting for current voting timer and blacklisted members")
async def show(interaction: discord.Interaction):
    guild = str(interaction.guild.id)
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    if guild not in config:
        config[guild] = Config(60, []).__dict__
    blacklist = ""
    for member in config[guild]["blacklist"]:
        blacklist += (await interaction.guild.fetch_member(member)).name + "\n"
    embed = discord.Embed(title="Secret Thrower Config")
    embed.add_field(name="Blacklist", value=blacklist)
    embed.add_field(name="Timer", value=config[guild]["timer"])
    await interaction.response.send_message(embed=embed, delete_after=60.0)

@client.event
async def on_ready():
    await tree.sync()
    if not os.path.exists("config.json"):
        with open("config.json", "w") as config:
            json.dump({}, config)
    print(f"{client.user} Ready!")

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
    #Need to get reactions and check that there isnt already a reaction for the current team
    for i, team in enumerate(teams):
        if reaction.emoji not in REACTIONS[i]:
            continue
        for j, player in enumerate(team.players):
            if REACTIONS[i][j][0] == reaction.emoji:
                player.count += 1
                if member.votes[i] != None:
                    await reaction.message.remove_reaction(get_reaction(game, member.votes[i]), user)
                member.votes[i] = player.member.id
                break
    team1_string, team2_string = list_players(game)
    embed = game.message.embeds[0]
    embed.set_field_at(0, name=embed.fields[0].name, value=team1_string)
    embed.set_field_at(1, name=embed.fields[1].name, value=team2_string)
    game.message = await game.message.edit(embed=embed)

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
        for j, player in enumerate(team.players):
            if REACTIONS[i][j][0] == reaction.emoji:
                player.count -= 1
                member.votes[i] = None
                break
    team1_string, team2_string = list_players(game)
    embed = game.message.embeds[0]
    embed.set_field_at(0, name=embed.fields[0].name, value=team1_string)
    embed.set_field_at(1, name=embed.fields[1].name, value=team2_string)
    game.message = await game.message.edit(embed=embed)

client.run(ENV["TOKEN"])