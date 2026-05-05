import discord
from discord.ext import commands
from discord import app_commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="")
    async def help(self, interaction: discord.Interaction):
        pass
        #Show life cycle commands
        #Show command options

async def setup(bot):
    await bot.add_cog(General(bot))