from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from constants import (
    BASE_RECENT,
    MAX_PLAYERS_PER_TEAM,
    MIN_PLAYERS_PER_TEAM,
    MIN_VOTING_TIMER,
    TEAM1_EMOJIS,
    TEAM2_EMOJIS,
    THROWER,
    VS_EMOJI,
    WINNER,
)
from data import Game, GameSettings, GameState, Player, Team
from database import (
    AsyncSessionLocal,
    delete_game_state,
    redis_client,
    save_game_state,
)
from elo import compute_elo_updates
from models import Game as DBGame
from models import Player as DBPlayer
from models import User as DBUser
from models import Vote as DBVote

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Setup UI
# ---------------------------------------------------------------------------


class GameSettingsModal(discord.ui.Modal, title="Game Settings"):
    voting_timer: discord.ui.TextInput = discord.ui.TextInput(
        label="Voting timer (seconds, min 10)",
        placeholder="60",
        required=True,
        min_length=1,
        max_length=4,
    )
    thrower_info: discord.ui.TextInput = discord.ui.TextInput(
        label="Throwers know teammates? (yes / no)",
        placeholder="no",
        required=True,
        min_length=2,
        max_length=3,
    )

    def __init__(self, game: "Game", cog: "GameCog") -> None:
        super().__init__()
        self._game = game
        self._cog = cog
        self.voting_timer.default = str(game.settings.voting_timer)
        self.thrower_info.default = "yes" if game.settings.thrower_info else "no"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            timer = int(self.voting_timer.value.strip())
        except ValueError:
            return await interaction.response.send_message("Voting timer must be a whole number.", ephemeral=True)
        if timer < MIN_VOTING_TIMER:
            return await interaction.response.send_message(
                f"Voting timer must be at least {MIN_VOTING_TIMER} seconds.", ephemeral=True
            )

        raw = self.thrower_info.value.strip().lower()
        if raw not in ("yes", "no", "y", "n"):
            return await interaction.response.send_message("Thrower info must be 'yes' or 'no'.", ephemeral=True)

        self._game.settings.voting_timer = timer
        self._game.settings.thrower_info = raw in ("yes", "y")

        await save_game_state(self._game.game_id, self._game.to_json())
        if self._game.message:
            await self._game.message.edit(embed=self._cog._build_embed(self._game))

        await interaction.response.send_message(
            f"Settings updated — Voting: **{timer}s** · "
            f"Thrower info: **{'on' if self._game.settings.thrower_info else 'off'}**",
            ephemeral=True,
        )


class SetupView(discord.ui.View):
    def __init__(self, game: "Game", cog: "GameCog") -> None:
        super().__init__(timeout=600)
        self._game = game
        self._cog = cog

    async def on_timeout(self) -> None:
        game = self._game
        if game.state != GameState.SETUP:
            # Game already started — timeout only applies to abandoned setup sessions
            return
        self._cog.active_games.get(game.guild_id, {}).pop(game.game_id, None)
        await delete_game_state(game.game_id)
        if game.message:
            try:
                await game.message.delete()
            except (discord.NotFound, discord.HTTPException):
                pass

    @discord.ui.button(label="⚙️ Game Settings", style=discord.ButtonStyle.secondary)
    async def settings_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not self._cog._is_host_or_mod(self._game, interaction):
            return await interaction.response.send_message(
                "Only the game host or a moderator can change settings.", ephemeral=True
            )
        await interaction.response.send_modal(GameSettingsModal(self._game, self._cog))


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------


class GameCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games: dict[int, dict[int, Game]] = {}  # guild_id -> {game_id -> Game}
        self._recovered = False

    game = app_commands.Group(name="game", description="Match lifecycle management")

    # ------------------------------------------------------------------
    # Error handler
    # ------------------------------------------------------------------

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            msg = "You don't have permission to use this command."
        else:
            cmd = interaction.command.name if interaction.command else "unknown"
            log.exception("Unhandled error in command '%s'", cmd, exc_info=error)
            msg = "Something went wrong. Please try again."

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    # ------------------------------------------------------------------
    # Restart recovery
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self._recovered:
            return
        self._recovered = True
        await self._recover_active_games()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        guild_games = self.active_games.get(payload.guild_id, {})
        game = next((g for g in guild_games.values() if g.game_id == payload.message_id), None)
        if not game or game.state != GameState.VOTING or not game.message:
            return

        emoji_str = str(payload.emoji)
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id) if guild else None
        if not member:
            return

        # Reject reactions that aren't valid voting emojis
        if emoji_str not in TEAM1_EMOJIS and emoji_str not in TEAM2_EMOJIS and emoji_str != VS_EMOJI:
            await game.message.remove_reaction(payload.emoji, member)
            return
        if emoji_str == VS_EMOJI:
            return

        # Remove reactions from non-players; allow players to react freely —
        # duplicates per team are resolved at vote-collection time (first vote wins).
        all_player_ids = {p.member.id for team in game.get_teams() for p in team.players}
        if payload.user_id not in all_player_ids:
            await game.message.remove_reaction(payload.emoji, member)
            return

    async def _recover_active_games(self) -> None:
        """On bot restart, reload SETUP/PLAYING games into memory and re-attach
        voting timers for any games that were mid-vote."""
        log.info("Scanning Redis for active games to recover...")
        recovered = 0

        async for key in redis_client.scan_iter("game:*"):
            try:
                json_str = await redis_client.get(key)
                if not json_str:
                    continue

                raw = json.loads(json_str)
                guild_id = raw["guild_id"]

                guild = self.bot.get_guild(guild_id)
                if not guild:
                    log.warning("Guild %d not found during recovery, skipping", guild_id)
                    continue

                game = Game.from_json(json_str)

                # Reconstruct team channel references
                team1_channel = guild.get_channel(raw["team1_channel_id"])
                team2_channel = guild.get_channel(raw["team2_channel_id"])
                if not team1_channel or not team2_channel:
                    log.warning("Team channels missing for guild %d, cleaning up", guild_id)
                    await delete_game_state(game.game_id)
                    continue

                def make_players(
                    ids: list[int],
                    _guild: discord.Guild,
                    thrower_ids: list[int],
                ) -> list[Player]:
                    result = []
                    for uid in ids:
                        member = _guild.get_member(uid)
                        if member:
                            p = Player(member=member)
                            p.is_thrower = uid in thrower_ids
                            result.append(p)
                    return result

                game.team1 = Team(
                    channel=team1_channel, players=make_players(raw["team1_player_ids"], guild, game.thrower_ids)
                )
                game.team2 = Team(
                    channel=team2_channel, players=make_players(raw["team2_player_ids"], guild, game.thrower_ids)
                )

                # Fetch the game embed message
                text_channel_id = raw.get("text_channel_id")
                if text_channel_id and game.game_id:
                    text_channel = guild.get_channel(text_channel_id)
                    if text_channel:
                        try:
                            game.message = await text_channel.fetch_message(game.game_id)
                        except (discord.NotFound, discord.Forbidden):
                            log.warning("Game message gone for guild %d, cleaning up", guild_id)
                            await delete_game_state(game.game_id)
                            continue

                self.active_games.setdefault(guild_id, {})[game.game_id] = game

                # Re-attach voting timer if it was in progress
                if game.state == GameState.VOTING and game.vote_end_timestamp:
                    remaining = game.vote_end_timestamp - time.time()
                    if remaining <= 0:
                        log.info("Voting expired during downtime for guild %d, revealing now", guild_id)
                        await self.reveal_results(game)
                    else:
                        log.info("Resuming voting timer for guild %d (%.0fs remaining)", guild_id, remaining)
                        game.voting_task = asyncio.create_task(self._run_voting_timer(game, delay=remaining))

                recovered += 1
                log.info("Recovered game for guild %d (state: %s)", guild_id, game.state.name)

            except Exception:
                log.exception("Error recovering game from Redis key '%s'", key)

        log.info("Recovery complete — restored %d active game(s)", recovered)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_game(self, interaction: discord.Interaction) -> Game | None:
        """Resolve the game this interaction targets.

        1. Invoker is the host of exactly one game → their game (owner path)
        2. Command channel matches a game's text channel → that game (mod path)
        3. Only one active game in the guild → fallback
        """
        guild_games = self.active_games.get(interaction.guild_id, {})
        if not guild_games:
            return None

        hosted = [g for g in guild_games.values() if g.host_id == interaction.user.id]
        if len(hosted) == 1:
            return hosted[0]

        matches = [g for g in guild_games.values() if g.text_channel_id == interaction.channel_id]
        if len(matches) == 1:
            return matches[0]

        if len(guild_games) == 1:
            return next(iter(guild_games.values()))

        return None

    def _no_game_msg(self, guild_id: int) -> str:
        if self.active_games.get(guild_id):
            return (
                "Multiple games are active. Run this command from the channel where your game "
                "was set up, or ask your game host to manage it."
            )
        return "No active game. Use `/game setup` first."

    def _channels_in_use(self, guild_id: int, channel_ids: set[int]) -> bool:
        for game in self.active_games.get(guild_id, {}).values():
            for team in game.get_teams():
                if team.channel.id in channel_ids:
                    return True
        return False

    def _is_host_or_mod(self, game: Game, interaction: discord.Interaction) -> bool:
        return interaction.user.id == game.host_id or interaction.user.guild_permissions.manage_guild

    @staticmethod
    def _team_name(game: Game, team_idx: int) -> str:
        team = game.get_teams()[team_idx]
        return team.channel.name if team else f"Team {team_idx + 1}"

    def _build_embed(self, game: Game) -> discord.Embed:
        color = discord.Color.blue() if game.state == GameState.SETUP else discord.Color.green()
        embed = discord.Embed(title="Secret Thrower", color=color)

        teams = game.get_teams()
        if game.state == GameState.VOTING:
            emoji_sets = [TEAM1_EMOJIS, TEAM2_EMOJIS]
            for team_idx, team in enumerate(teams):
                lines = [f"{emoji_sets[team_idx][i]} {p.member.display_name}" for i, p in enumerate(team.players)]
                embed.add_field(name=self._team_name(game, team_idx), value="\n".join(lines), inline=True)
                if team_idx == 0:
                    embed.add_field(name="​", value="​", inline=True)
        else:
            for team_idx, team in enumerate(teams):
                player_list = "\n".join(p.member.display_name for p in team.players) or "No players"
                name = self._team_name(game, team_idx)
                if game.winning_channel_id and game.winning_channel_id == team.channel.id:
                    name = f"{WINNER} {name}"
                embed.add_field(name=name, value=player_list, inline=True)

        if game.state == GameState.SETUP:
            embed.set_footer(
                text=f"Voting: {game.settings.voting_timer}s  ·  "
                f"Thrower info: {'on' if game.settings.thrower_info else 'off'}"
            )

        return embed

    @staticmethod
    def _weighted_sample(population: list[int], weights: dict[int, float], k: int) -> list[int]:
        """Weighted sampling without replacement."""
        remaining = {uid: w for uid, w in weights.items() if uid in population}
        selected: list[int] = []
        for _ in range(min(k, len(remaining))):
            chosen = random.choices(list(remaining.keys()), weights=list(remaining.values()))[0]
            selected.append(chosen)
            del remaining[chosen]
        return selected

    async def _get_thrower_weights(self, session: AsyncSession, player_ids: list[int]) -> dict[int, float]:
        """Single query for all players — players who haven't thrown recently get higher weight."""
        if not player_ids:
            return {}

        result = await session.execute(
            select(DBPlayer.user_id, DBPlayer.is_thrower)
            .join(DBGame, DBPlayer.game_id == DBGame.game_id)
            .where(DBPlayer.user_id.in_(player_ids))
            .order_by(DBPlayer.user_id, DBGame.created_at.desc())
        )
        rows = result.all()

        # Group by player, keep only the 10 most recent records per player
        records: dict[int, list[bool]] = defaultdict(list)
        for user_id, is_thrower in rows:
            if len(records[user_id]) < 10:
                records[user_id].append(is_thrower)

        return {uid: BASE_RECENT + sum(1 for t in records.get(uid, []) if not t) for uid in player_ids}

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @game.command(name="setup", description="Initialize a Secret Thrower game from two voice channels")
    @app_commands.describe(team1="Voice channel for team 1", team2="Voice channel for team 2")
    async def setup(
        self,
        interaction: discord.Interaction,
        team1: discord.VoiceChannel,
        team2: discord.VoiceChannel,
    ) -> None:
        guild_id = interaction.guild_id

        if team1.id == team2.id:
            return await interaction.response.send_message("Teams must be different voice channels.", ephemeral=True)
        if not team1.members or not team2.members:
            return await interaction.response.send_message(
                "Both voice channels must have at least one member.", ephemeral=True
            )
        if self._channels_in_use(guild_id, {team1.id, team2.id}):
            return await interaction.response.send_message(
                "One or both of those voice channels are already part of an active game.", ephemeral=True
            )

        game = Game(guild_id=guild_id)
        game.settings = GameSettings()
        game.host_id = interaction.user.id
        game.text_channel_id = interaction.channel_id
        game.team1 = Team(channel=team1, players=[Player(member=m) for m in team1.members])
        game.team2 = Team(channel=team2, players=[Player(member=m) for m in team2.members])

        embed = self._build_embed(game)
        await interaction.response.send_message("Game created!", ephemeral=True, delete_after=5.0)
        game.message = await interaction.channel.send(embed=embed, view=SetupView(game, self))
        game.game_id = game.message.id

        self.active_games.setdefault(guild_id, {})[game.game_id] = game
        await save_game_state(game.game_id, game.to_json())
        log.info("Game created in guild %d by user %d", guild_id, interaction.user.id)

    @game.command(name="add", description="Add or move a player to a team")
    @app_commands.describe(team="The team's voice channel", user="The player to add or move")
    async def add(
        self,
        interaction: discord.Interaction,
        team: discord.VoiceChannel,
        user: discord.Member,
    ) -> None:
        game = self._get_game(interaction)

        if game is None:
            return await interaction.response.send_message(self._no_game_msg(interaction.guild_id), ephemeral=True)
        if game.state != GameState.SETUP:
            return await interaction.response.send_message("Players can only be added during setup.", ephemeral=True)
        if not self._is_host_or_mod(game, interaction):
            return await interaction.response.send_message(
                "Only the game host or a server moderator can modify players.", ephemeral=True
            )
        if team.id != game.team1.channel.id and team.id != game.team2.channel.id:
            return await interaction.response.send_message(
                f"Unknown team. Options: **{game.team1.channel.name}**, **{game.team2.channel.name}**",
                ephemeral=True,
            )

        for t in game.get_teams():
            t.players = [p for p in t.players if p.member.id != user.id]

        target_team = game.team1 if team.id == game.team1.channel.id else game.team2
        target_team.players.append(Player(member=user))

        await game.message.edit(embed=self._build_embed(game))
        await save_game_state(game.game_id, game.to_json())
        await interaction.response.send_message(
            f"Added **{user.display_name}** to **{team.name}**.", ephemeral=True, delete_after=30.0
        )

    @game.command(name="remove", description="Remove a player from the game")
    @app_commands.describe(user="The player to remove")
    async def remove(self, interaction: discord.Interaction, user: discord.Member) -> None:
        game = self._get_game(interaction)

        if game is None:
            return await interaction.response.send_message(self._no_game_msg(interaction.guild_id), ephemeral=True)
        if game.state != GameState.SETUP:
            return await interaction.response.send_message("Players can only be removed during setup.", ephemeral=True)
        if not self._is_host_or_mod(game, interaction):
            return await interaction.response.send_message(
                "Only the game host or a server moderator can modify players.", ephemeral=True
            )

        for team in game.get_teams():
            for player in team.players:
                if player.member.id == user.id:
                    team.players.remove(player)
                    await game.message.edit(embed=self._build_embed(game))
                    await save_game_state(game.game_id, game.to_json())
                    return await interaction.response.send_message(
                        f"Removed **{user.display_name}** from the game.", ephemeral=True, delete_after=30.0
                    )

        await interaction.response.send_message(f"**{user.display_name}** is not in the game.", ephemeral=True)

    @game.command(name="cancel", description="Cancel the current game")
    async def cancel(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        game = self._get_game(interaction)

        if game is None:
            return await interaction.response.send_message("No active game to cancel.", ephemeral=True)
        if not self._is_host_or_mod(game, interaction):
            return await interaction.response.send_message(
                "Only the game host or a server moderator can cancel the game.", ephemeral=True
            )

        if game.voting_task and not game.voting_task.done():
            game.voting_task.cancel()

        if game.message:
            try:
                await game.message.delete()
            except discord.NotFound:
                pass

        await delete_game_state(game.game_id)
        self.active_games.get(guild_id, {}).pop(game.game_id, None)
        log.info("Game cancelled in guild %d by user %d", guild_id, interaction.user.id)
        await interaction.response.send_message("Game cancelled.", ephemeral=True, delete_after=30.0)

    @game.command(name="start", description="Assign secret throwers and begin the game")
    @app_commands.describe(
        team1_count="Number of secret throwers on team 1 (default 1)",
        team2_count="Number of secret throwers on team 2 (default 1)",
    )
    async def start(
        self,
        interaction: discord.Interaction,
        team1_count: int = 1,
        team2_count: int = 1,
    ) -> None:
        guild_id = interaction.guild_id
        game = self._get_game(interaction)

        if game is None:
            return await interaction.response.send_message(self._no_game_msg(interaction.guild_id), ephemeral=True)
        if game.state != GameState.SETUP:
            return await interaction.response.send_message("Game is already in progress.", ephemeral=True)
        if not self._is_host_or_mod(game, interaction):
            return await interaction.response.send_message(
                "Only the game host or a server moderator can start the game.", ephemeral=True
            )
        for team in (game.team1, game.team2):
            # TODO Probably remove the min players?
            if len(team.players) < MIN_PLAYERS_PER_TEAM:
                return await interaction.response.send_message(
                    f"**{team.channel.name}** needs at least {MIN_PLAYERS_PER_TEAM} players "
                    f"(currently {len(team.players)}). Use `/game add` to fill the team.",
                    ephemeral=True,
                )
            if len(team.players) > MAX_PLAYERS_PER_TEAM:
                return await interaction.response.send_message(
                    f"**{team.channel.name}** has {len(team.players)} players but the voting UI "
                    f"supports a maximum of {MAX_PLAYERS_PER_TEAM} per team. Use `/game remove` to trim it.",
                    ephemeral=True,
                )

        await interaction.response.defer(ephemeral=True)

        team1_count = min(team1_count, len(game.team1.players))
        team2_count = min(team2_count, len(game.team2.players))

        all_ids = [p.member.id for p in game.team1.players + game.team2.players]
        async with AsyncSessionLocal() as session:
            weights = await self._get_thrower_weights(session, all_ids)

        for team, count in [(game.team1, team1_count), (game.team2, team2_count)]:
            team_ids = [p.member.id for p in team.players]
            for uid in self._weighted_sample(team_ids, weights, count):
                game.thrower_ids.append(uid)
                for player in team.players:
                    if player.member.id == uid:
                        player.is_thrower = True

        failed_dms: list[str] = []
        for team in game.get_teams():
            team_throwers = [p for p in team.players if p.is_thrower]
            for player in team_throwers:
                msg = (
                    "You are the **Secret Thrower**!\n"
                    "Your goal is to lose the game without being discovered by the other players."
                )
                if game.settings.thrower_info:
                    partners = [t for t in team_throwers if t.member.id != player.member.id]
                    if partners:
                        names = ", ".join(p.member.display_name for p in partners)
                        msg += f"\nYour partner(s) on this team: **{names}**"
                    else:
                        msg += "\nYou are the only thrower on your team."
                try:
                    await player.member.send(msg)
                except discord.Forbidden:
                    failed_dms.append(player.member.display_name)
                    log.warning(
                        "Could not DM thrower %d (%s) in guild %d", player.member.id, player.member.name, guild_id
                    )

        game.state = GameState.PLAYING
        await save_game_state(game.game_id, game.to_json())
        log.info("Game started in guild %d — throwers: %s", guild_id, game.thrower_ids)

        if game.message:
            try:
                await game.message.edit(view=None)
            except discord.NotFound:
                pass

        reply = f"Secret Throwers assigned — Team 1: {team1_count}, Team 2: {team2_count}"
        if failed_dms:
            reply += f"\n⚠️ Could not DM: {', '.join(failed_dms)} (they have DMs disabled — notify them manually)."
        await interaction.followup.send(reply, ephemeral=True)
        await interaction.channel.send("Secret Throwers have been assigned. Let the game begin!", delete_after=60.0)

    @game.command(name="result", description="Declare the winning team and start the voting phase")
    @app_commands.describe(winner="The voice channel of the winning team")
    async def result(self, interaction: discord.Interaction, winner: discord.VoiceChannel) -> None:
        guild_id = interaction.guild_id
        game = self._get_game(interaction)

        if game is None:
            return await interaction.response.send_message(self._no_game_msg(interaction.guild_id), ephemeral=True)
        if game.state != GameState.PLAYING:
            return await interaction.response.send_message(
                "The game must be started before declaring a result. Use `/game start` first.",
                ephemeral=True,
            )
        if not self._is_host_or_mod(game, interaction):
            return await interaction.response.send_message(
                "Only the game host or a server moderator can declare a result.", ephemeral=True
            )
        if winner.id != game.team1.channel.id and winner.id != game.team2.channel.id:
            return await interaction.response.send_message(
                f"Unknown team. Options: **{game.team1.channel.name}**, **{game.team2.channel.name}**",
                ephemeral=True,
            )

        game.winning_channel_id = winner.id
        game.state = GameState.VOTING
        game.vote_end_timestamp = int(time.time()) + game.settings.voting_timer

        winner_team_idx = 0 if winner.id == game.team1.channel.id else 1
        winner_display = self._team_name(game, winner_team_idx)

        embed = self._build_embed(game)
        embed.description = (
            f"{WINNER} **{winner_display}** wins!\n"
            f"Vote for the secret thrower on each team. Voting ends <t:{game.vote_end_timestamp}:R>"
        )

        await save_game_state(game.game_id, game.to_json())

        await interaction.response.send_message(f"**{winner_display}** wins! Voting has started.", delete_after=10.0)
        await game.message.edit(embed=embed, view=None)

        # Add reactions: team 1 emojis ⚔️ team 2 emojis
        for i in range(len(game.team1.players)):
            await game.message.add_reaction(TEAM1_EMOJIS[i])
        await game.message.add_reaction(VS_EMOJI)
        for i in range(len(game.team2.players)):
            await game.message.add_reaction(TEAM2_EMOJIS[i])

        game.voting_task = asyncio.create_task(self._run_voting_timer(game))
        log.info("Voting started in guild %d — winner channel: %d", guild_id, winner.id)

    # ------------------------------------------------------------------
    # Voting helpers
    # ------------------------------------------------------------------

    async def _run_voting_timer(self, game: Game, delay: float | None = None) -> None:
        try:
            await asyncio.sleep(delay if delay is not None else float(game.settings.voting_timer))
            await self.reveal_results(game)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Voting timer failed for game %d in guild %d", game.game_id, game.guild_id)

    async def _collect_votes(self, game: Game, message: discord.Message) -> dict[int, dict[int, int]]:
        """Build votes dict from message reactions. voter_id → {team_idx → target_player_id}."""
        teams = game.get_teams()
        all_player_ids = {p.member.id for team in teams for p in team.players}
        votes: dict[int, dict[int, int]] = {}
        emoji_sets = [TEAM1_EMOJIS, TEAM2_EMOJIS]

        for team_idx, team in enumerate(teams):
            for slot, player in enumerate(team.players):
                emoji = emoji_sets[team_idx][slot]
                reaction = discord.utils.get(message.reactions, emoji=emoji)
                if not reaction:
                    continue
                async for user in reaction.users():
                    if user.bot or user.id not in all_player_ids:
                        continue
                    votes.setdefault(user.id, {}).setdefault(team_idx, player.member.id)

        return votes

    # ------------------------------------------------------------------
    # Result reveal — called by voting timer
    # ------------------------------------------------------------------

    async def reveal_results(self, game: Game) -> None:
        """Reads reactions, clears them, builds results embed, commits to DB."""
        # Fetch fresh message so reaction counts are current
        try:
            message = await game.message.channel.fetch_message(game.message.id)
        except discord.NotFound:
            log.warning(
                "Voting message deleted for game %d in guild %d",
                game.game_id,
                game.guild_id,
            )
            message = game.message
        except discord.HTTPException:
            message = game.message

        votes = await self._collect_votes(game, message)

        try:
            await message.clear_reactions()
        except (discord.HTTPException, discord.Forbidden):
            pass

        teams = game.get_teams()
        vote_counts: list[dict[int, int]] = [{p.member.id: 0 for p in team.players} for team in teams]
        for team_votes in votes.values():
            for team_idx, target_id in team_votes.items():
                if target_id in vote_counts[team_idx]:
                    vote_counts[team_idx][target_id] += 1

        embed = discord.Embed(title="Secret Thrower — Results", color=discord.Color.gold())

        winner_team_idx = next((i for i, t in enumerate(teams) if t.channel.id == game.winning_channel_id), None)
        winner_name = self._team_name(game, winner_team_idx) if winner_team_idx is not None else "Unknown"
        summary_lines = [f"{WINNER} **{winner_name}** wins!\n"]

        for team_idx, team in enumerate(teams):
            lines = []
            for player in team.players:
                count = vote_counts[team_idx].get(player.member.id, 0)
                prefix = f"{THROWER} " if player.is_thrower else ""
                lines.append(f"{prefix}**{player.member.display_name}** — {count} vote(s)")
            team_display = self._team_name(game, team_idx)
            embed.add_field(name=team_display, value="\n".join(lines) or "No players", inline=True)

            if any(v > 0 for v in vote_counts[team_idx].values()):
                most_voted_id = max(vote_counts[team_idx], key=vote_counts[team_idx].get)
                thrower_ids = {p.member.id for p in team.players if p.is_thrower}
                if most_voted_id in thrower_ids:
                    summary_lines.append(f"{team_display}: Thrower **caught**! 🎯")
                else:
                    summary_lines.append(f"{team_display}: Thrower **escaped**! 😈")

        embed.description = "\n".join(summary_lines)

        try:
            await game.message.edit(embed=embed, view=None)
        except (discord.NotFound, discord.HTTPException):
            pass

        try:
            await self._commit_game(game, votes)
        except Exception:
            log.exception("Failed to commit game for guild %d — state preserved in Redis for recovery", game.guild_id)
            return

        await delete_game_state(game.game_id)
        self.active_games.get(game.guild_id, {}).pop(game.game_id, None)
        log.info("Game completed in guild %d", game.guild_id)

    async def _commit_game(self, game: Game, votes: dict[int, dict[int, int]]) -> None:
        """Persists the completed game and applies stat + ELO updates."""
        teams = game.get_teams()

        async with AsyncSessionLocal() as session:
            db_users: dict[int, DBUser] = {}
            for team in teams:
                for player in team.players:
                    db_user = await session.get(DBUser, player.member.id)
                    if db_user:
                        db_user.username = player.member.name
                    else:
                        db_user = DBUser(user_id=player.member.id, username=player.member.name)
                        session.add(db_user)
                    db_users[player.member.id] = db_user

            # Flush so column defaults are populated before the counters below increment them
            await session.flush()

            session.add(
                DBGame(
                    game_id=game.game_id,
                    guild_id=game.guild_id,
                    winning_channel_id=game.winning_channel_id,
                )
            )
            await session.flush()

            for team in teams:
                for player in team.players:
                    session.add(
                        DBPlayer(
                            game_id=game.game_id,
                            user_id=player.member.id,
                            channel_id=team.channel.id,
                            is_thrower=player.is_thrower,
                        )
                    )

            for voter_id, team_votes in votes.items():
                for target_id in team_votes.values():
                    session.add(DBVote(game_id=game.game_id, voter_id=voter_id, target_id=target_id))

            for team in teams:
                team_won = team.channel.id == game.winning_channel_id
                for player in team.players:
                    db_user = db_users[player.member.id]
                    db_user.games_played += 1
                    if team_won:
                        db_user.games_won += 1
                        db_user.win_streak += 1
                        db_user.best_win_streak = max(db_user.best_win_streak, db_user.win_streak)
                    else:
                        db_user.win_streak = 0
                    if player.is_thrower:
                        db_user.games_as_thrower += 1
                        if not team_won:
                            db_user.games_thrown += 1

            for voter_id, team_votes in votes.items():
                voter = db_users.get(voter_id)
                for target_id in team_votes.values():
                    target = db_users.get(target_id)
                    if voter:
                        voter.total_votes_cast += 1
                    if target:
                        target.total_votes_received += 1
                        if target_id in game.thrower_ids:
                            if voter:
                                voter.votes_cast_on_thrower += 1
                            target.votes_received_as_thrower += 1

            roster = [[(p.member.id, p.is_thrower) for p in team.players] for team in teams]
            winning_team_idx = next(
                (i for i, team in enumerate(teams) if team.channel.id == game.winning_channel_id), None
            )
            ratings = {user_id: (u.innocent_elo, u.thrower_elo) for user_id, u in db_users.items()}

            for user_id, update in compute_elo_updates(roster, votes, winning_team_idx, ratings).items():
                db_user = db_users[user_id]
                db_user.innocent_elo = update.innocent_elo
                db_user.thrower_elo = update.thrower_elo
                if update.evaded:
                    db_user.games_evaded += 1

            await session.commit()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GameCog(bot))
