import logging
import os

import discord
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy import text

from database import AsyncSessionLocal

log = logging.getLogger(__name__)

_SUPPORT_URL = os.getenv("SUPPORT_URL", "")
_SUPPORT_DISCORD = os.getenv("SUPPORT_DISCORD", "")


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._db_keepalive.start()

    def cog_unload(self):
        self._db_keepalive.cancel()

    @tasks.loop(hours=24)  # every day — Supabase pauses after 7
    async def _db_keepalive(self):
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            log.info("DB keepalive ping succeeded.")
        except Exception as exc:
            log.warning("DB keepalive failed: %s", exc)

    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(title="Secret Thrower Help", color=discord.Color.green())
        embed.add_field(name="Setup", value="`/game setup` — Initialize teams from voice channels", inline=False)
        embed.add_field(
            name="Gameplay",
            value=("`/game start` — Assign secret throwers\n`/game result` — Declare winner and start voting"),
            inline=False,
        )
        embed.add_field(
            name="Management",
            value=(
                "`/game add` — Add/move a player\n"
                "`/game remove` — Remove a player\n"
                "`/game cancel` — Cancel the current game"
            ),
            inline=False,
        )
        embed.add_field(
            name="Settings",
            value="Configured per-game via the ⚙️ button on the game embed after `/game setup`.",
            inline=False,
        )
        embed.add_field(
            name="Stats",
            value=("`/profile stats` — View your stats and ELO\n`/profile leaderboard` — Server rankings\n"),
            inline=False,
        )
        if _SUPPORT_URL:
            support_text = f"[Join our support server]({_SUPPORT_URL})"
        elif _SUPPORT_DISCORD:
            support_text = f"DM <@{_SUPPORT_DISCORD}> for help."
        else:
            support_text = "Contact the bot administrator for help."
        embed.add_field(name="Support", value=support_text, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(General(bot))
