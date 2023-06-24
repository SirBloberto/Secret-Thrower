import discord
from bot import tree
from constants import *
from utils import *

@tree.command(name="statistics", description="Get statistics on Secret-Thrower player")
async def statistics(interaction: discord.Interaction):
    user=interaction.user.id
    embed = discord.Embed(title="Player Statistics")
    games_played=cursor.execute(f"SELECT COUNT(*) FROM player WHERE user_id={user}").fetchone()[0]
    wins=cursor.execute(f"SELECT COUNT(*) FROM team WHERE channel_id = (SELECT channel_id FROM player WHERE game_id=team.game_id and user_id={user}) and winner=1").fetchone()[0]
    thrower_games=cursor.execute(f"SELECT COUNT(*) from player WHERE user_id={user} and thrower=1").fetchone()[0]
    games_thrown=cursor.execute(f"SELECT COUNT(*) FROM team WHERE channel_id = (SELECT channel_id FROM player WHERE game_id=team.game_id and user_id={user} and thrower=1) and winner=0").fetchone()[0]
    votes_received=cursor.execute(f"SELECT COUNT(*) from vote WHERE vote={user}").fetchone()[0]
    votes_received_as_thrower=cursor.execute(f"SELECT count(*) FROM vote WHERE vote={user} and game_id = (SELECT game_id FROM player WHERE user_id={user} and thrower=1)").fetchone()[0]
    votes_sent=cursor.execute(f"SELECT COUNT(*) from vote WHERE user_id={user}").fetchone()[0]
    votes_sent_on_thrower=cursor.execute(f"SELECT count(*) FROM vote WHERE user_id={user} and vote IN (SELECT user_id FROM player WHERE game_id=vote.game_id and thrower=1)").fetchone()[0]
    values=[games_played, wins, thrower_games, games_thrown, votes_received, votes_received_as_thrower, votes_sent, votes_sent_on_thrower]
    embed.add_field(name="Statistic", value=''.join(str(statistic) + '\n' for statistic in STATISTIC_NAMES))
    embed.add_field(name="Value", value=''.join(str(value) + '\n' for value in values))
    favourite_votes = cursor.execute(f"SELECT username, COUNT(vote) FROM vote INNER JOIN user on vote.vote = user.user_id WHERE vote.user_id={user} GROUP BY vote ORDER by COUNT(vote) DESC LIMIT 3").fetchall()
    names=[]
    vote_count=[]
    for record in favourite_votes:
        names.append(record[0])
        vote_count.append(record[1])
    embed.add_field(name = "Favourite Players to Vote", value="", inline=False)
    embed.add_field(name = "Player", value=''.join(str(value) + '\n' for value in names))
    embed.add_field(name = "Vote count", value=''.join(str(value) + '\n' for value in vote_count))
    await interaction.response.send_message(embed=embed)