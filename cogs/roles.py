from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from database import AsyncSessionLocal, is_premium
from models import GuildEloRole
from models import User as DBUser


class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    roles = app_commands.Group(name="roles", description="Configure ELO role assignments")
    elo_group = app_commands.Group(name="elo", description="Manage ELO tier → Discord role mappings", parent=roles)

    async def _guard(self, interaction: discord.Interaction) -> bool:
        """Check Manage Roles permission and Premium status. Sends an error and returns False if either fails."""
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "❌ You need **Manage Roles** permission.", ephemeral=True
            )
            return False
        if not await is_premium(interaction.guild_id):
            await interaction.response.send_message(
                "❌ ELO role assignment is a **Premium** feature. Use `/subscribe` to unlock it.", ephemeral=True
            )
            return False
        return True

    async def _sync_guild_roles(self, guild: discord.Guild) -> str:
        """Assign ELO roles to all guild members based on their current ELO. Returns a human-readable summary."""
        async with AsyncSessionLocal() as session:
            mappings = (
                await session.execute(select(GuildEloRole).where(GuildEloRole.guild_id == guild.id))
            ).scalars().all()

        if not mappings:
            return "no mappings configured"

        member_ids = [m.id for m in guild.members]
        async with AsyncSessionLocal() as session:
            db_users = {
                u.user_id: u
                for u in (
                    await session.execute(
                        select(DBUser).where(DBUser.user_id.in_(member_ids), DBUser.games_played > 0)
                    )
                ).scalars()
            }

        innocent_tiers = sorted([m for m in mappings if m.elo_type == "innocent"], key=lambda m: m.min_elo, reverse=True)
        thrower_tiers  = sorted([m for m in mappings if m.elo_type == "thrower"],  key=lambda m: m.min_elo, reverse=True)
        all_tier_role_ids = {m.role_id for m in mappings}

        assigned = removed = skipped = 0
        for member in guild.members:
            db_user = db_users.get(member.id)
            if not db_user:
                continue

            target_role_ids: set[int] = set()
            for tier in innocent_tiers:
                if db_user.innocent_elo >= tier.min_elo:
                    target_role_ids.add(tier.role_id)
                    break
            for tier in thrower_tiers:
                if db_user.thrower_elo >= tier.min_elo:
                    target_role_ids.add(tier.role_id)
                    break

            current_role_ids = {r.id for r in member.roles}
            to_add = [guild.get_role(rid) for rid in target_role_ids if rid not in current_role_ids and guild.get_role(rid)]
            to_remove = [guild.get_role(rid) for rid in all_tier_role_ids if rid not in target_role_ids and rid in current_role_ids and guild.get_role(rid)]

            try:
                if to_remove:
                    await member.remove_roles(*to_remove, reason="ELO tier update")
                    removed += len(to_remove)
                if to_add:
                    await member.add_roles(*to_add, reason="ELO tier update")
                    assigned += len(to_add)
            except discord.Forbidden:
                # Stop immediately — this is a server-wide permission problem, not per-member
                return "❌ Missing Manage Roles permission — run `/roles elo check` for the fix"
            except discord.HTTPException:
                skipped += 1

        parts = []
        if assigned:
            parts.append(f"{assigned} role(s) assigned")
        if removed:
            parts.append(f"{removed} role(s) removed")
        if skipped:
            parts.append(f"{skipped} skipped (API error)")
        return " · ".join(parts) if parts else "no changes needed"

    @elo_group.command(name="add", description="Map an ELO tier to a Discord role")
    @app_commands.describe(
        elo_type="Which ELO track",
        min_elo="Minimum ELO to receive this role (0–100)",
        role="Discord role to assign at this tier",
    )
    @app_commands.choices(elo_type=[
        app_commands.Choice(name="Innocent", value="innocent"),
        app_commands.Choice(name="Thrower", value="thrower"),
    ])
    async def elo_add(
        self,
        interaction: discord.Interaction,
        elo_type: app_commands.Choice[str],
        min_elo: int,
        role: discord.Role,
    ) -> None:
        if not await self._guard(interaction):
            return
        if not (0 <= min_elo <= 100):
            return await interaction.response.send_message(
                "❌ `min_elo` must be between 0 and 100.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        async with AsyncSessionLocal() as session:
            existing = (
                await session.execute(
                    select(GuildEloRole).where(
                        GuildEloRole.guild_id == interaction.guild_id,
                        GuildEloRole.role_id == role.id,
                    )
                )
            ).scalar_one_or_none()

            if existing:
                existing.elo_type = elo_type.value
                existing.min_elo = float(min_elo)
                action = "Updated"
            else:
                session.add(GuildEloRole(
                    guild_id=interaction.guild_id,
                    elo_type=elo_type.value,
                    min_elo=float(min_elo),
                    role_id=role.id,
                ))
                action = "Added"
            await session.commit()

        sync = await self._sync_guild_roles(interaction.guild)
        await interaction.followup.send(
            f"✅ {action} — {role.mention} assigned at **{elo_type.name} ELO ≥ {min_elo}**.\n"
            f"Sync: {sync}",
            ephemeral=True,
        )

    @elo_group.command(name="remove", description="Remove an ELO role mapping")
    @app_commands.describe(role="The Discord role to unmap")
    async def elo_remove(self, interaction: discord.Interaction, role: discord.Role) -> None:
        if not await self._guard(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(
                    select(GuildEloRole).where(
                        GuildEloRole.guild_id == interaction.guild_id,
                        GuildEloRole.role_id == role.id,
                    )
                )
            ).scalar_one_or_none()

            if not row:
                return await interaction.followup.send(
                    f"❌ {role.mention} is not mapped to any ELO tier.", ephemeral=True
                )
            await session.delete(row)
            await session.commit()

        sync = await self._sync_guild_roles(interaction.guild)
        await interaction.followup.send(
            f"✅ Removed mapping for {role.mention}.\nSync: {sync}",
            ephemeral=True,
        )

    @elo_group.command(name="check", description="Verify the bot can assign all configured ELO roles")
    async def elo_check(self, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.manage_roles:
            return await interaction.response.send_message(
                "❌ You need **Manage Roles** permission.", ephemeral=True
            )

        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    select(GuildEloRole).where(GuildEloRole.guild_id == interaction.guild_id)
                )
            ).scalars().all()

        if not rows:
            return await interaction.response.send_message(
                "No ELO roles configured. Use `/roles elo add` to set one up.", ephemeral=True
            )

        bot_member = interaction.guild.get_member(self.bot.user.id)
        bot_top = bot_member.top_role.position if bot_member else 0

        lines: list[str] = []
        all_ok = True

        # Check the bot has Manage Roles permission — without this, all role assignments fail
        if not bot_member or not bot_member.guild_permissions.manage_roles:
            lines.append(
                "❌ **Bot is missing Manage Roles permission**\n"
                "Fix: Server Settings → Roles → Secret Thrower → enable **Manage Roles**"
            )
            all_ok = False

        for r in rows:
            role = interaction.guild.get_role(r.role_id)
            if not role:
                lines.append(f"⚠️ Deleted role (id `{r.role_id}`) — remove it with `/roles elo remove`")
                all_ok = False
            elif role.position >= bot_top:
                lines.append(f"❌ {role.mention} — drag **Secret Thrower** above this role")
                all_ok = False
            else:
                label = "Innocent" if r.elo_type == "innocent" else "Thrower"
                lines.append(f"✅ {role.mention} ({label} ELO ≥ {r.min_elo:.0f})")

        embed = discord.Embed(
            title="ELO Role Check",
            description="\n".join(lines),
            color=discord.Color.green() if all_ok else discord.Color.red(),
        )
        if not all_ok:
            embed.set_footer(text="Server Settings → Roles → Secret Thrower → enable Manage Roles + drag it above your ELO roles")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @elo_group.command(name="sync", description="Re-sync ELO roles for all server members now")
    async def elo_sync(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        result = await self._sync_guild_roles(interaction.guild)
        await interaction.followup.send(f"Sync complete: {result}", ephemeral=True)

    @elo_group.command(name="list", description="Show all configured ELO role mappings")
    async def elo_list(self, interaction: discord.Interaction) -> None:
        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    select(GuildEloRole)
                    .where(GuildEloRole.guild_id == interaction.guild_id)
                    .order_by(GuildEloRole.elo_type, GuildEloRole.min_elo.desc())
                )
            ).scalars().all()

        if not rows:
            return await interaction.response.send_message(
                "No ELO roles configured. Use `/roles elo add` to set one up.", ephemeral=True
            )

        lines = [
            f"{interaction.guild.get_role(r.role_id).mention if interaction.guild.get_role(r.role_id) else f'*(deleted role {r.role_id})*'}"
            f" — {'Innocent' if r.elo_type == 'innocent' else 'Thrower'} ELO ≥ **{r.min_elo:.0f}**"
            for r in rows
        ]
        embed = discord.Embed(
            title="ELO Role Assignments",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Roles(bot))
