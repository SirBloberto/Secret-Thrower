from __future__ import annotations

import time
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import func, select

from achievements import ACHIEVEMENTS, format_achievements
from constants import ELO_STARTING
from database import AsyncSessionLocal, is_premium
from models import Game as DBGame
from models import Player as DBPlayer
from models import User as DBUser
from models import Vote as DBVote

_LEGEND_BASE = "Suspect Accuracy: % of votes you placed on a real thrower  •  Heat: avg votes against you per game"
_LEGEND_THROWER = "  •  Throw Rate: team lost as thrower  •  Clean Throw: threw + not most accused"

_MEDALS = ["🥇", "🥈", "🥉"]

# Guild member list is cached per guild for this many seconds to avoid repeated Discord API calls.
_MEMBER_CACHE_TTL = 300

_CATEGORIES: dict[str, dict] = {
    "innocent_elo": {
        "label": "🏆 Innocent ELO",
        "sort_key": lambda u: u.innocent_elo,
        "fmt": lambda u: f"{u.innocent_elo:.0f}",
        "eligible": lambda u: u.games_played >= 3,
        "footer": "Sorted by Innocent ELO — min 3 games",
    },
    "thrower_elo": {
        "label": "🕵️ Thrower ELO",
        "sort_key": lambda u: u.thrower_elo,
        "fmt": lambda u: f"{u.thrower_elo:.0f}",
        "eligible": lambda u: u.games_as_thrower >= 3,
        "footer": "Sorted by Thrower ELO — min 3 games as thrower",
    },
    "suspect_accuracy": {
        "label": "🔍 Suspect Accuracy",
        "sort_key": lambda u: u.votes_cast_on_thrower / u.total_votes_cast if u.total_votes_cast >= 10 else -1.0,
        "fmt": lambda u: (
            f"{u.votes_cast_on_thrower / u.total_votes_cast * 100:.0f}%"
            f" ({u.votes_cast_on_thrower}/{u.total_votes_cast})"
        ),
        "eligible": lambda u: u.total_votes_cast >= 10,
        "footer": "Sorted by Suspect Accuracy — min 10 votes cast",
    },
    "evasion": {
        "label": "🎯 Evasion Rate",
        "sort_key": lambda u: u.games_evaded / u.games_as_thrower if u.games_as_thrower >= 3 else -1.0,
        "fmt": lambda u: f"{u.games_evaded / u.games_as_thrower * 100:.0f}% ({u.games_evaded}/{u.games_as_thrower})",
        "eligible": lambda u: u.games_as_thrower >= 3,
        "footer": "Sorted by Clean Throw Rate — min 3 games as thrower",
    },
}


def _pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "—"
    return f"{numerator / denominator * 100:.0f}%"


def _heat(votes: int, games: int) -> str:
    if games == 0:
        return "—"
    return f"{votes / games:.1f}/game"


def _leaderboard_embed(members: dict[int, discord.Member], users: list[DBUser], category_key: str) -> discord.Embed:
    cat = _CATEGORIES[category_key]
    eligible = sorted(
        (u for u in users if cat["eligible"](u)),
        key=cat["sort_key"],
        reverse=True,
    )[:10]

    embed = discord.Embed(
        title=f"Secret Thrower — {cat['label']} Leaderboard",
        color=discord.Color.gold(),
    )
    embed.set_footer(text=cat["footer"])

    lines: list[str] = []
    for i, db_user in enumerate(eligible):
        prefix = _MEDALS[i] if i < 3 else f"`{i + 1}.`"
        member = members.get(db_user.user_id)
        name = member.display_name if member else "Unknown"
        lines.append(f"{prefix} **{name}** — {cat['fmt'](db_user)}")

    embed.description = "\n".join(lines) or "No players meet the minimum requirement yet."
    return embed


class LeaderboardView(discord.ui.View):
    def __init__(self, members: dict[int, discord.Member], users: list[DBUser], initial: str = "innocent_elo"):
        super().__init__(timeout=120)
        self.members = members
        self.users = users
        self.current = initial

    async def _switch(self, interaction: discord.Interaction, category: str) -> None:
        self.current = category
        await interaction.response.edit_message(
            embed=_leaderboard_embed(self.members, self.users, self.current), view=self
        )

    @discord.ui.button(label="🏆 Innocent ELO", style=discord.ButtonStyle.primary, row=0)
    async def btn_innocent(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._switch(interaction, "innocent_elo")

    @discord.ui.button(label="🕵️ Thrower ELO", style=discord.ButtonStyle.primary, row=0)
    async def btn_thrower(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._switch(interaction, "thrower_elo")

    @discord.ui.button(label="🔍 Suspect Accuracy", style=discord.ButtonStyle.secondary, row=0)
    async def btn_accuracy(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._switch(interaction, "suspect_accuracy")

    @discord.ui.button(label="🎯 Evasion Rate", style=discord.ButtonStyle.secondary, row=0)
    async def btn_evasion(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._switch(interaction, "evasion")


class UserProfiles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> (member_dict, timestamp)
        self._member_cache: dict[int, tuple[dict[int, discord.Member], float]] = {}

    async def _get_guild_members(self, guild: discord.Guild) -> dict[int, discord.Member]:
        cached = self._member_cache.get(guild.id)
        if cached and time.monotonic() - cached[1] < _MEMBER_CACHE_TTL:
            return cached[0]
        members: dict[int, discord.Member] = {}
        async for member in guild.fetch_members(limit=None):
            members[member.id] = member
        self._member_cache[guild.id] = (members, time.monotonic())
        return members

    profile = app_commands.Group(name="profile", description="Profile management for Secret Thrower")

    @profile.command(name="stats", description="View statistics for a Secret Thrower player")
    async def stats(self, interaction: discord.Interaction, user: discord.Member = None) -> None:
        target = user or interaction.user

        await interaction.response.defer()

        # Use cached member list for guild filtering (avoids Discord API call on every stats request).
        guild_members = await self._get_guild_members(interaction.guild)
        member_ids = list(guild_members.keys())

        async with AsyncSessionLocal() as session:
            db_user = await session.get(DBUser, target.id)

            avg_acc = (
                await session.execute(
                    select(func.avg(DBUser.votes_cast_on_thrower * 1.0 / DBUser.total_votes_cast)).where(
                        DBUser.user_id.in_(member_ids),
                        DBUser.total_votes_cast >= 10,
                    )
                )
            ).scalar()

            avg_evasion = (
                await session.execute(
                    select(func.avg(DBUser.games_evaded * 1.0 / DBUser.games_as_thrower)).where(
                        DBUser.user_id.in_(member_ids),
                        DBUser.games_as_thrower >= 3,
                    )
                )
            ).scalar()

            avg_heat_thrower = (
                await session.execute(
                    select(func.avg(DBUser.votes_received_as_thrower * 1.0 / DBUser.games_as_thrower)).where(
                        DBUser.user_id.in_(member_ids),
                        DBUser.games_as_thrower >= 1,
                    )
                )
            ).scalar()

            avg_heat_innocent = (
                await session.execute(
                    select(
                        func.avg(
                            (DBUser.total_votes_received - DBUser.votes_received_as_thrower)
                            * 1.0
                            / (DBUser.games_played - DBUser.games_as_thrower)
                        )
                    ).where(
                        DBUser.user_id.in_(member_ids),
                        (DBUser.games_played - DBUser.games_as_thrower) >= 1,
                    )
                )
            ).scalar()

        if db_user is None:
            return await interaction.followup.send(
                f"**{target.display_name}** has not played any games yet.", ephemeral=True
            )

        avg_acc = float(avg_acc or 0.0)
        avg_evasion = float(avg_evasion or 0.0)
        avg_heat_thrower = float(avg_heat_thrower or 0.0)
        avg_heat_innocent = float(avg_heat_innocent or 0.0)

        gp = db_user.games_played
        innocent_games = gp - db_user.games_as_thrower
        failed_throws = db_user.games_as_thrower - db_user.games_thrown
        innocent_wins = max(0, db_user.games_won - failed_throws)
        innocent_votes_received = max(0, db_user.total_votes_received - db_user.votes_received_as_thrower)

        embed = discord.Embed(title=f"Stats — {target.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=target.display_avatar.url)
        footer = _LEGEND_BASE + (_LEGEND_THROWER if db_user.games_as_thrower > 0 else "")
        embed.set_footer(text=footer)

        # Row 1 — overview
        embed.add_field(name="🎮 Games", value=f"**{gp}**", inline=True)
        embed.add_field(
            name="🏆 Win Rate",
            value=f"**{_pct(innocent_wins, innocent_games)}** ({innocent_wins}W as innocent)",
            inline=True,
        )
        embed.add_field(name="​", value="​", inline=True)

        # Row 2 — skill
        embed.add_field(
            name="🔍 Suspect Accuracy",
            value=f"**{_pct(db_user.votes_cast_on_thrower, db_user.total_votes_cast)}** "
            f"({db_user.votes_cast_on_thrower}/{db_user.total_votes_cast})",
            inline=True,
        )
        embed.add_field(
            name="🕵️ Throw Rate",
            value=(
                f"**{_pct(db_user.games_thrown, db_user.games_as_thrower)}** "
                f"({db_user.games_thrown}/{db_user.games_as_thrower})"
                if db_user.games_as_thrower > 0
                else "**—** (never assigned)"
            ),
            inline=True,
        )
        embed.add_field(
            name="🎯 Clean Throws",
            value=(
                f"**{_pct(db_user.games_evaded, db_user.games_as_thrower)}** "
                f"({db_user.games_evaded} / {db_user.games_as_thrower})"
                if db_user.games_as_thrower > 0
                else "**—**"
            ),
            inline=True,
        )

        # Row 3 — heat
        embed.add_field(
            name="🌡️ Heat as Thrower",
            value=f"**{_heat(db_user.votes_received_as_thrower, db_user.games_as_thrower)}**",
            inline=True,
        )
        embed.add_field(
            name="🧊 Heat as Innocent",
            value=f"**{_heat(innocent_votes_received, innocent_games)}**",
            inline=True,
        )
        embed.add_field(name="​", value="​", inline=True)

        # Spacer
        embed.add_field(name="​", value="​", inline=False)

        # Row 4 — ELO
        def _elo_str(elo: float) -> str:
            delta = elo - ELO_STARTING
            sign = "+" if delta >= 0 else ""
            return f"**{elo:.0f}** ({sign}{delta:.0f} vs avg)"

        embed.add_field(
            name="📊 ELO (1–100)",
            value=f"Innocent {_elo_str(db_user.innocent_elo)} · Thrower {_elo_str(db_user.thrower_elo)}",
            inline=False,
        )

        # Spacer
        embed.add_field(name="​", value="​", inline=False)

        # Row 5 — server averages
        embed.add_field(
            name="📈 Server Averages",
            value=(
                f"🌡️ Thrower {avg_heat_thrower:.1f}/game  🧊 Innocent {avg_heat_innocent:.1f}/game\n"
                f"🔍 Accuracy {avg_acc * 100:.0f}%  🎯 Evasion {avg_evasion * 100:.0f}%"
            ),
            inline=False,
        )

        await interaction.followup.send(embed=embed)

    @profile.command(name="history", description="View your last 10 games [Premium]")
    @app_commands.describe(user="Player to view (default: yourself)", role="Filter by role")
    @app_commands.choices(role=[
        app_commands.Choice(name="Thrower", value="thrower"),
        app_commands.Choice(name="Innocent", value="innocent"),
    ])
    async def history(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
        role: app_commands.Choice[str] = None,
    ) -> None:
        if not await is_premium(interaction.guild_id):
            return await interaction.response.send_message(
                "📊 Game history is a **Premium** feature. Ask a server admin to use `/subscribe`.",
                ephemeral=True,
            )

        target = user or interaction.user
        await interaction.response.defer(ephemeral=True)

        async with AsyncSessionLocal() as session:
            # Last 10 games for this player in this guild
            query = (
                select(DBPlayer, DBGame)
                .join(DBGame, DBPlayer.game_id == DBGame.game_id)
                .where(DBPlayer.user_id == target.id, DBGame.guild_id == interaction.guild_id)
            )
            if role is not None:
                query = query.where(DBPlayer.is_thrower == (role.value == "thrower"))
            rows = (
                await session.execute(query.order_by(DBGame.created_at.desc()).limit(10))
            ).all()

            if not rows:
                return await interaction.followup.send(
                    f"**{target.display_name}** has no recorded games in this server.", ephemeral=True
                )

            game_ids = [g.game_id for _, g in rows]

            # Batch fetch all votes and all players for those games
            all_votes = (
                await session.execute(select(DBVote).where(DBVote.game_id.in_(game_ids)))
            ).scalars().all()

            all_players = (
                await session.execute(select(DBPlayer).where(DBPlayer.game_id.in_(game_ids)))
            ).scalars().all()

        # Index for fast lookup
        votes_by_game: dict[int, list[DBVote]] = defaultdict(list)
        for v in all_votes:
            votes_by_game[v.game_id].append(v)

        players_by_game: dict[int, list[DBPlayer]] = defaultdict(list)
        for p in all_players:
            players_by_game[p.game_id].append(p)

        lines: list[str] = []
        wins = losses = 0

        for player_row, game in rows:
            team_won = player_row.channel_id == game.winning_channel_id
            if team_won:
                wins += 1
            else:
                losses += 1

            # Discord relative timestamp — shows local date on hover
            ts = f"<t:{int(game.created_at.timestamp())}:d>"
            result = "✅" if team_won else "❌"

            game_votes = votes_by_game[game.game_id]
            game_players = players_by_game[game.game_id]
            thrower_ids = {p.user_id for p in game_players if p.is_thrower}

            if player_row.is_thrower:
                team_player_ids = {p.user_id for p in game_players if p.channel_id == player_row.channel_id}
                tally: dict[int, int] = {uid: 0 for uid in team_player_ids}
                for v in game_votes:
                    if v.target_id in tally:
                        tally[v.target_id] += 1
                most_accused = max(tally, key=tally.get) if any(tally.values()) else None
                detail = "🎯 Caught" if most_accused == target.id else "😈 Evaded"
                lines.append(f"{ts} {result} 🕵️ Thrower · {detail}")
            else:
                my_votes = [v for v in game_votes if v.voter_id == target.id]
                if my_votes:
                    correct = sum(1 for v in my_votes if v.target_id in thrower_ids)
                    all_correct = correct == len(my_votes)
                    detail = f"🔍 {'All correct' if all_correct else f'{correct}/{len(my_votes)} correct'}"
                else:
                    detail = "🔍 Didn't vote"
                lines.append(f"{ts} {result} 👤 Innocent · {detail}")

        thrower_count = sum(1 for p, _ in rows if p.is_thrower)
        innocent_count = len(rows) - thrower_count

        role_label = f" · {role.name} games" if role else ""
        embed = discord.Embed(
            title=f"Game History — {target.display_name}{role_label}",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        total = wins + losses
        role_breakdown = f"🕵️ {thrower_count}×  👤 {innocent_count}×  ·  " if role is None else ""
        embed.set_footer(text=f"{role_breakdown}{wins}W – {losses}L in last {total}  ·  Premium")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @profile.command(name="achievements", description="View achievement progress for a player")
    @app_commands.describe(user="Player to view (default: yourself)")
    async def achievements(self, interaction: discord.Interaction, user: discord.Member = None) -> None:
        target = user or interaction.user
        await interaction.response.defer(ephemeral=True)

        async with AsyncSessionLocal() as session:
            db_user = await session.get(DBUser, target.id)

        if db_user is None:
            return await interaction.followup.send(
                f"**{target.display_name}** has not played any games yet.", ephemeral=True
            )

        earned = bin(db_user.achievements).count("1")
        total = len(ACHIEVEMENTS)
        embed = discord.Embed(
            title=f"Achievements — {target.display_name}",
            description=f"**{earned}/{total}** earned\n\n{format_achievements(db_user.achievements, db_user)}",
            color=discord.Color.gold(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        if db_user.best_win_streak > 0:
            embed.set_footer(text=f"Best win streak: {db_user.best_win_streak} · Current: {db_user.win_streak}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @profile.command(name="leaderboard", description="Show top players ranked by various stats")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        guild_members = await self._get_guild_members(interaction.guild)
        member_ids = list(guild_members.keys())

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DBUser).where(DBUser.games_played > 0, DBUser.user_id.in_(member_ids))
            )
            users = result.scalars().all()

        if not users:
            return await interaction.followup.send("No players from this server found.", ephemeral=True)

        view = LeaderboardView(guild_members, users)
        embed = _leaderboard_embed(guild_members, users, "innocent_elo")
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UserProfiles(bot))
