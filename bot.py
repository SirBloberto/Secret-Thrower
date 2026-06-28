import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


class SecretThrowerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True  # needed to read voice channel members and guild member cache

        super().__init__(command_prefix="/", intents=intents)

    async def setup_hook(self):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename != "__init__.py":
                await self.load_extension(f"cogs.{filename[:-3]}")
                log.info("Loaded cog: %s", filename[:-3])

        await self.tree.sync()
        log.info("Slash commands synced.")

    async def on_ready(self):
        log.info("%s is online!", self.user)


bot = SecretThrowerBot()
bot.run(os.getenv("DISCORD_TOKEN"))
