"""Reaction-based voting flow, ELO, and achievement tests — no live Discord or DB required.

Run all tests:        uv run pytest tests/ -v
Run just this file:   uv run pytest tests/test_game_flow.py -v
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cogs.game import GameCog
from constants import MAX_PLAYERS_PER_TEAM, TEAM1_EMOJIS, TEAM2_EMOJIS, VS_EMOJI
from data import Game, GameSettings, GameState, Player, Team


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _member(uid: int, *, bot: bool = False) -> MagicMock:
    m = MagicMock()
    m.id = uid
    m.display_name = f"User{uid}"
    m.bot = bot
    return m


def _channel(cid: int, name: str) -> MagicMock:
    ch = MagicMock()
    ch.id = cid
    ch.name = name
    return ch


def _game(
    team1_ids: list[int],
    team2_ids: list[int],
    *,
    thrower1_id: int | None = None,
    thrower2_id: int | None = None,
    winning_channel_id: int = 100,
) -> Game:
    """Build a minimal Game in VOTING state."""
    g = Game(guild_id=1)
    g.game_id = 12345
    g.state = GameState.VOTING
    g.settings = GameSettings(voting_timer=60)
    g.winning_channel_id = winning_channel_id

    t1 = []
    for uid in team1_ids:
        p = Player(member=_member(uid))
        p.is_thrower = uid == thrower1_id
        t1.append(p)

    t2 = []
    for uid in team2_ids:
        p = Player(member=_member(uid))
        p.is_thrower = uid == thrower2_id
        t2.append(p)

    g.team1 = Team(channel=_channel(100, "Team Alpha"), players=t1)
    g.team2 = Team(channel=_channel(200, "Team Beta"), players=t2)
    return g


class _AsyncIter:
    """Async iterator over a static list — fakes discord's reaction.users()."""

    def __init__(self, items: list) -> None:
        self._items = list(items)

    def __aiter__(self) -> _AsyncIter:
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


def _message(reactions: dict[str, list[int]]) -> MagicMock:
    """Fake discord.Message whose reactions list mirrors the given dict.

    reactions maps emoji_str → [user IDs who reacted with that emoji].
    """
    msg = MagicMock()
    mocks = []
    for emoji_str, voter_ids in reactions.items():
        r = MagicMock()
        r.emoji = emoji_str
        users_items = [_member(uid) for uid in voter_ids]
        r.users = MagicMock(side_effect=lambda items=users_items: _AsyncIter(list(items)))
        mocks.append(r)
    msg.reactions = mocks
    return msg


def _mock_user(**kwargs) -> MagicMock:
    """Fake models.User with default zero stats."""
    defaults = dict(
        games_played=0,
        games_won=0,
        games_as_thrower=0,
        games_thrown=0,
        games_evaded=0,
        votes_cast_on_thrower=0,
        total_votes_cast=0,
        innocent_elo=50.0,
        achievements=0,
        win_streak=0,
        best_win_streak=0,
    )
    defaults.update(kwargs)
    return MagicMock(**defaults)


def _cog() -> GameCog:
    return GameCog(MagicMock())


# ---------------------------------------------------------------------------
# Voting emoji sanity
# ---------------------------------------------------------------------------


def test_emoji_sets_cover_max_players():
    assert len(TEAM1_EMOJIS) >= MAX_PLAYERS_PER_TEAM
    assert len(TEAM2_EMOJIS) >= MAX_PLAYERS_PER_TEAM


def test_emoji_sets_are_disjoint():
    """An emoji can only vote for one team — the two sets must not overlap."""
    assert not set(TEAM1_EMOJIS) & set(TEAM2_EMOJIS)


def test_vs_emoji_not_in_voting_sets():
    """The separator emoji must not be a valid vote."""
    assert VS_EMOJI not in TEAM1_EMOJIS
    assert VS_EMOJI not in TEAM2_EMOJIS


# ---------------------------------------------------------------------------
# _collect_votes — core voting logic
# ---------------------------------------------------------------------------


async def test_collect_votes_basic():
    """Each player votes for one player per team — both votes recorded correctly."""
    # Team 1: [11 (thrower), 12]   Team 2: [21 (thrower), 22]
    # Voter 12 clicks 🇦 (→ team1[0] = uid 11) and 1️⃣ (→ team2[0] = uid 21)
    # Voter 11 clicks 🇧 (→ team1[1] = uid 12) and 2️⃣ (→ team2[1] = uid 22)
    game = _game([11, 12], [21, 22], thrower1_id=11, thrower2_id=21)
    msg = _message({
        TEAM1_EMOJIS[0]: [12],
        TEAM1_EMOJIS[1]: [11],
        TEAM2_EMOJIS[0]: [12],
        TEAM2_EMOJIS[1]: [11],
    })

    votes = await _cog()._collect_votes(game, msg)

    assert votes[12][0] == 11   # voter 12 accused team1 player 11
    assert votes[12][1] == 21   # voter 12 accused team2 player 21
    assert votes[11][0] == 12   # voter 11 accused team1 player 12
    assert votes[11][1] == 22   # voter 11 accused team2 player 22


async def test_collect_votes_non_players_ignored():
    """Reactions from users not in the game are silently dropped."""
    game = _game([11, 12], [21, 22])
    msg = _message({TEAM1_EMOJIS[0]: [99]})  # uid 99 is not a player

    votes = await _cog()._collect_votes(game, msg)

    assert votes == {}


async def test_collect_votes_bot_reactions_ignored():
    """The bot adds reactions to the message — those must not count as votes."""
    game = _game([11], [21])
    r = MagicMock()
    r.emoji = TEAM1_EMOJIS[0]
    bot_user = MagicMock()
    bot_user.id = 999
    bot_user.bot = True
    r.users = MagicMock(return_value=_AsyncIter([bot_user]))
    msg = MagicMock()
    msg.reactions = [r]

    votes = await _cog()._collect_votes(game, msg)

    assert votes == {}


async def test_collect_votes_partial_vote_one_team_only():
    """Player votes for team 1 but not team 2 — only team 1 vote is recorded."""
    game = _game([11, 12], [21, 22])
    msg = _message({TEAM1_EMOJIS[0]: [12]})

    votes = await _cog()._collect_votes(game, msg)

    assert votes == {12: {0: 11}}
    assert 1 not in votes.get(12, {})  # no team 2 vote


async def test_collect_votes_no_reactions():
    """Voting period with no reactions → empty votes dict."""
    game = _game([11, 12], [21, 22])
    msg = _message({})

    votes = await _cog()._collect_votes(game, msg)

    assert votes == {}


async def test_collect_votes_multiple_voters_same_target():
    """Several players can vote for the same person — all votes are recorded."""
    game = _game([11, 12], [21, 22])
    msg = _message({TEAM1_EMOJIS[0]: [11, 12]})  # both vote for team1[0] (uid 11)

    votes = await _cog()._collect_votes(game, msg)

    assert votes[11][0] == 11
    assert votes[12][0] == 11


# ---------------------------------------------------------------------------
# _k_factor — ELO update scaling
# ---------------------------------------------------------------------------


def test_k_factor_at_starting_elo_equals_base_k():
    from constants import ELO_K, ELO_STARTING
    k = GameCog._k_factor(float(ELO_STARTING), +1.0)
    assert abs(k - ELO_K) < 0.01


def test_k_factor_gaining_elo_is_easier_at_low_elo():
    """Rising from ELO 20 should give more points per win than from ELO 80."""
    k_low = GameCog._k_factor(20.0, +1.0)
    k_high = GameCog._k_factor(80.0, +1.0)
    assert k_low > k_high


def test_k_factor_losing_elo_is_harsher_at_high_elo():
    """A high-ELO player loses more per loss to preserve rank rarity."""
    k_low = GameCog._k_factor(20.0, -1.0)
    k_high = GameCog._k_factor(80.0, -1.0)
    assert k_high > k_low


def test_k_factor_is_always_positive():
    for elo in [0.0, 25.0, 50.0, 75.0, 100.0]:
        assert GameCog._k_factor(elo, +1.0) > 0
        assert GameCog._k_factor(elo, -1.0) > 0


# ---------------------------------------------------------------------------
# Achievement logic
# ---------------------------------------------------------------------------


def test_first_blood_unlocks_after_first_game():
    from achievements import check_new_achievements
    user = _mock_user(games_played=1)
    mask = check_new_achievements(user)
    assert mask & (1 << 0), "First Blood (bit 0) should unlock after 1 game"


def test_sharp_eye_unlocks_at_ten_correct_votes():
    from achievements import check_new_achievements
    user = _mock_user(games_played=1, votes_cast_on_thrower=10)
    mask = check_new_achievements(user)
    assert mask & (1 << 1), "Sharp Eye (bit 1) should unlock at 10 correct votes"


def test_no_achievements_for_new_player():
    from achievements import check_new_achievements
    user = _mock_user()
    assert check_new_achievements(user) == 0


def test_already_held_achievement_not_re_emitted():
    """check_new_achievements returns only *newly* earned bits."""
    from achievements import check_new_achievements
    user = _mock_user(games_played=1, achievements=1)  # already holds First Blood
    mask = check_new_achievements(user)
    assert not (mask & (1 << 0)), "First Blood already held — should not be in newly mask"


def test_multiple_achievements_unlock_at_once():
    from achievements import check_new_achievements
    user = _mock_user(games_played=1, votes_cast_on_thrower=10)
    mask = check_new_achievements(user)
    assert mask & (1 << 0)  # First Blood
    assert mask & (1 << 1)  # Sharp Eye


# ---------------------------------------------------------------------------
# Per-game achievements (check_game_achievements)
# ---------------------------------------------------------------------------


def test_double_vision_unlocks_when_found_both():
    from achievements import check_game_achievements
    user = _mock_user()
    mask = check_game_achievements(user, found_both=True)
    assert mask & (1 << 8), "Double Vision (bit 8) should unlock when both throwers found"


def test_lone_wolf_unlocks_when_sole_correct_voter():
    from achievements import check_game_achievements
    user = _mock_user()
    mask = check_game_achievements(user, lone_correct=True)
    assert mask & (1 << 9), "Lone Wolf (bit 9) should unlock when only correct voter"


def test_phantom_unlocks_when_thrower_gets_zero_votes():
    from achievements import check_game_achievements
    user = _mock_user()
    mask = check_game_achievements(user, perfect_throw=True)
    assert mask & (1 << 10), "Phantom (bit 10) should unlock when thrower receives no votes"


def test_game_achievements_not_re_emitted_if_already_held():
    from achievements import check_game_achievements
    held = (1 << 8) | (1 << 9) | (1 << 10)
    user = _mock_user(achievements=held)
    mask = check_game_achievements(user, found_both=True, lone_correct=True, perfect_throw=True)
    assert mask == 0, "Already-held per-game achievements must not be re-emitted"


def test_hot_streak_unlocks_at_five_wins():
    from achievements import check_new_achievements
    user = _mock_user(best_win_streak=5, win_streak=5)
    mask = check_new_achievements(user)
    assert mask & (1 << 11), "Hot Streak (bit 11) should unlock at best_win_streak >= 5"


def test_unstoppable_unlocks_at_ten_wins():
    from achievements import check_new_achievements
    user = _mock_user(best_win_streak=10, win_streak=10)
    mask = check_new_achievements(user)
    assert mask & (1 << 11)  # Hot Streak too
    assert mask & (1 << 12), "Unstoppable (bit 12) should unlock at best_win_streak >= 10"


def test_per_game_flags_all_false_yields_nothing():
    from achievements import check_game_achievements
    user = _mock_user()
    assert check_game_achievements(user) == 0
