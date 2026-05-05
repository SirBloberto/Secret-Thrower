import discord
from discord.ext import commands
from discord import app_commands
from constants import STATISTIC_NAMES
from models import User, Subscription

class UserProfiles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    profile = app_commands.Group(name="profile", description="Profile management for Secret Thrower")

    @profile.command(name="stats", description="Get statistics on Secret-Thrower player")
    async def stats(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        user_id = target.id

        embed = discord.Embed(
            title=f"Player statistics for {target.display_name}",
            color=discord.Color.blue()
        )

        result = cursor.execute("SELECT a,b,c,d FROM user WHERE user_id=%s", (user_id,))

        #Populate
        #Check for premium otherwise display all stats?
        embed.add_field(name="Statistic", value=stats_list, inline=True)
        embed.add_field(name="Value", value=values_list, inline=True)
        
        await interaction.response.send_message(embed=embed)

    @profile.command(name="leaderboard", description="View the top players (Premium Only)")
    async def leaderboard(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Global Leaderboard", color=discord.Color.gold())
        embed.add_field(name="Top Throwers", value="1. PlayerA\n2. PlayerB")
        #There should be elo system, both for being the thrower and being a player. Need to determine how this is calculate. Store in the user column
        #Should be based off the number of your win/throw percentage, voting accuracy. Potentially if we want to get crazy, relative voting. Ex: Everyone guessed the thrower and they have low elo
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(UserProfiles(bot))