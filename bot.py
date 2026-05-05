import discord
import json
import os
from dotenv import dotenv_values
from utils import *

ENV = dotenv_values(".env")

class SecretThrowerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        intents.members = True
        intents.reactions = True
        
        super().__init__(command_prefix="/", intents=intents)

    async def setup_hook(self):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename != "__init__.py":
                await self.load_extension(f"cogs.{filename[:-3]}")
        
        await self.tree.sync()

    async def on_ready(self):
        print(f'{self.user} is online!')

bot = SecretThrowerBot()
bot.run(ENV["TOKEN"])[cite: 5]