import asyncio
import logging
import os

_SUPPORT_URL = os.getenv("SUPPORT_URL", "")
_SUPPORT_DISCORD = os.getenv("SUPPORT_DISCORD", "")

import discord
import stripe
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy import select, text

from database import AsyncSessionLocal, is_premium
from models import Subscription

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "https://discord.com")
_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "https://discord.com")

log = logging.getLogger(__name__)


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._db_keepalive.start()

    def cog_unload(self):
        self._db_keepalive.cancel()

    @tasks.loop(hours=144)  # every 6 days — Supabase pauses after 7
    async def _db_keepalive(self):
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            log.info("DB keepalive ping succeeded.")
        except Exception as exc:
            log.warning("DB keepalive failed: %s", exc)

    @app_commands.command(name="subscribe", description="Subscribe this server to Secret Thrower Premium")
    async def subscribe(self, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message(
                "❌ You need **Manage Server** permission to subscribe.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        if await is_premium(interaction.guild_id):
            return await interaction.followup.send(
                "✅ This server already has **Secret Thrower Premium** active.", ephemeral=True
            )

        if not _PRICE_ID:
            return await interaction.followup.send(
                "❌ Subscriptions are not yet configured. Please contact the bot developer.", ephemeral=True
            )

        try:
            session = await asyncio.to_thread(
                stripe.checkout.Session.create,
                mode="subscription",
                line_items=[{"price": _PRICE_ID, "quantity": 1}],
                metadata={"guild_id": str(interaction.guild_id)},
                subscription_data={"metadata": {"guild_id": str(interaction.guild_id)}},
                success_url=_SUCCESS_URL,
                cancel_url=_CANCEL_URL,
            )
        except stripe.StripeError as exc:
            log.error("Stripe Checkout creation failed for guild %d: %s", interaction.guild_id, exc)
            return await interaction.followup.send(
                "❌ Failed to create a checkout session. Please try again later.", ephemeral=True
            )

        await interaction.followup.send(
            "💳 **Secret Thrower Premium — $4/month**\n\n"
            f"[Click here to subscribe]({session.url})\n\n"
            "Premium unlocks game history, ELO role assignment, and more. "
            "Your server is activated instantly after payment.",
            ephemeral=True,
        )

    @app_commands.command(name="subscribe_status", description="Check this server's Premium subscription status")
    async def subscribe_status(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(select(Subscription).where(Subscription.target_id == interaction.guild_id))
            ).scalar_one_or_none()

        if not row or not row.is_active:
            return await interaction.followup.send(
                "❌ This server does not have an active Premium subscription.\n"
                "Use `/subscribe` to unlock Premium features.",
                ephemeral=True,
            )

        expires = f"<t:{int(row.expires_at.timestamp())}:R>" if row.expires_at else "never"
        await interaction.followup.send(
            f"✅ **Secret Thrower Premium** is active on this server.\nRenews {expires}.",
            ephemeral=True,
        )

    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(title="Secret Thrower Help", color=discord.Color.green())
        embed.add_field(name="Setup", value="`/game setup` — Initialize teams from voice channels", inline=False)
        embed.add_field(
            name="Gameplay",
            value=(
                "`/game start` — Assign secret throwers\n"
                "`/game result` — Declare winner and start voting"
            ),
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
            value=(
                "`/profile stats` — View your stats and ELO\n"
                "`/profile leaderboard` — Server rankings\n"
                "`/profile achievements` — View earned badges and progress"
            ),
            inline=False,
        )
        embed.add_field(
            name="Premium",
            value=(
                "`/subscribe` — Unlock Premium (requires Manage Server)\n"
                "`/subscribe_status` — Check if this server has Premium\n"
                "`/game customize` — Custom team names and embed color\n"
                "`/roles elo add` — Map ELO tiers to Discord roles\n"
                "`/roles elo sync` — Re-sync ELO roles for all members\n"
                "`/roles elo check` — Verify the bot can assign roles\n"
                "`/profile history` — View your last 10 games"
            ),
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
