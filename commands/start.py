import discord
import json
import random
from datetime import datetime
from bot import games, tree
from data import *
from utils import *

@tree.command(name="start", description='Assign the secret throwers and start the game')
@discord.app_commands.describe(team1_count="Number of secret throwers on team1")
@discord.app_commands.describe(team2_count="Number of secret throwers on team2")
async def start(interaction: discord.Interaction, team1_count: int = 1, team2_count: int = 1):
    global games
    global random
    global datetime

    guild = interaction.guild
    game = get_game(games, guild)

    if game == None:
        return await interaction.response.send_message("Not in a game! Use /create to start a Secret-Thrower game", ephemeral=True, delete_after=60.0)
    if game.state != State.STARTING:
        return await interaction.response.send_message(game_state(game.state, State.STARTING), ephemeral=True, delete_after=60.0)
    
    with open('config.json', 'r') as config_in:
        config = json.load(config_in)
    
    thrower_info = config[str(guild.id)]['thrower_info']
    player_recent = cursor.execute(f"SELECT * FROM v_recent WHERE user_id IN ({','.join([str(player.member.id) for player in (game.team1.players + game.team2.players)])})").fetchall()
    recent = dict((player, recent) for player, recent in player_recent)
    probability=[]
    players = [game.team1.players, game.team2.players]
    for index in range(2):
        probability.append({})
        for player in players[index]:
            probability[index][player.member.id] = (recent[player.member.id] if player.member.id in recent else 0) + BASE_RECENT
    
    team1_count = len(game.team1.players) if len(game.team1.players) < team1_count else team1_count
    team2_count = len(game.team2.players) if len(game.team2.players) < team2_count else team2_count
    for _ in range(team1_count):
        thrower = random.choices(list(probability[0].keys()), weights=list(probability[0].values()))[0]
        game.throwers[0].append(id_to_player(game, thrower))
        del probability[0][thrower]
    for _ in range(team2_count):
        thrower = random.choices(list(probability[1].keys()), weights=list(probability[1].values()))[0]
        game.throwers[1].append(id_to_player(game, thrower))
        del probability[1][thrower]
    
    for index in range(2):
        for player in game.throwers[index]:
            message="You are the secret thrower! Your goal is to lose the game without being discovered by others. "
            if thrower_info:
                team_throwers=[thrower for thrower in game.throwers[index] if thrower != player]
                if len(team_throwers) == 0:
                    message+="You are alone."
                elif len(team_throwers) == 1:
                    message+="Your partner is: " + team_throwers[0].member.name
                elif len(team_throwers) >= 2:
                    message+="Your partners are: " + "".join(str(thrower.member.name) + ", " for thrower in team_throwers)
            await player.member.send(message)
    
    game.state = State.PLAYING
    await interaction.response.send_message(f"Secret Thrower count -> Team1: {team1_count}, Team2: {team2_count}", ephemeral=not thrower_info, delete_after=60.0)
    await interaction.channel.send("Secret Throwers have been assigned", delete_after=60.0)
    game_time = datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')
    
    cursor.execute(f"INSERT INTO guild (guild_id) SELECT {game.guild.id} WHERE NOT EXISTS (SELECT * FROM guild WHERE guild_id = {game.guild.id})")
    cursor.execute(f"INSERT INTO game (game_id, game_time, guild_id, info) VALUES ({game.message.id}, ?, {game.guild.id}, ?)", (game_time, game.info,))
    
    teams = [game.team1, game.team2]
    for index, team in enumerate(teams):
        cursor.execute(f"INSERT INTO channel (channel_id) SELECT {team.team.id} WHERE NOT EXISTS (SELECT * FROM channel WHERE channel_id = {team.team.id})")
        cursor.execute(f"INSERT INTO team (game_id, channel_id, winner) VALUES ({game.message.id}, {team.team.id}, 0)")
        
        for player in team.players:
            cursor.execute(f"INSERT INTO user (user_id, username) SELECT {player.member.id}, ? WHERE NOT EXISTS (SELECT * FROM user WHERE user_id = {player.member.id})", (player.member.name,))
            cursor.execute(f"INSERT INTO player (game_id, channel_id, user_id, thrower) VALUES ({game.message.id}, {team.team.id}, {player.member.id}, {int(any(thrower.member.id == player.member.id for thrower in game.throwers[index]))})")
    connection.commit()