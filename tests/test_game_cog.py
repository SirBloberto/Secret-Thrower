from __future__ import annotations

from unittest.mock import MagicMock

from cogs.game import GameCog
from constants import MAX_PLAYERS_PER_TEAM, MIN_PLAYERS_PER_TEAM, TEAM1_EMOJIS, TEAM2_EMOJIS
from data import Game, GameSettings, GameState, Player, Team


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


class _AsyncIter:
    def __init__(self, items: list) -> None:
        self._items = list(items)

    def __aiter__(self) -> _AsyncIter:
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


def _message(reactions: dict[str, list[int]]) -> MagicMock:
    msg = MagicMock()
    mocks = []
    for emoji_str, voter_ids in reactions.items():
        r = MagicMock()
        r.emoji = emoji_str
        users = [_member(uid) for uid in voter_ids]
        r.users = MagicMock(side_effect=lambda items=users: _AsyncIter(list(items)))
        mocks.append(r)
    msg.reactions = mocks
    return msg


def _game(
    team1_ids: list[int],
    team2_ids: list[int],
    *,
    thrower1_id: int | None = None,
    thrower2_id: int | None = None,
    winning_channel_id: int = 100,
) -> Game:
    g = Game(guild_id=1)
    g.game_id = 12345
    g.state = GameState.VOTING
    g.settings = GameSettings(voting_timer=60)
    g.winning_channel_id = winning_channel_id

    def players(ids: list[int], thrower_id: int | None) -> list[Player]:
        out = []
        for uid in ids:
            p = Player(member=_member(uid))
            p.is_thrower = uid == thrower_id
            out.append(p)
        return out

    g.team1 = Team(channel=_channel(100, "Team Alpha"), players=players(team1_ids, thrower1_id))
    g.team2 = Team(channel=_channel(200, "Team Beta"), players=players(team2_ids, thrower2_id))
    return g


def _cog() -> GameCog:
    return GameCog(MagicMock())


async def test_collect_votes():
    game = _game([11, 12], [21, 22], thrower1_id=11, thrower2_id=21)
    msg = _message(
        {
            TEAM1_EMOJIS[0]: [12],
            TEAM1_EMOJIS[1]: [11],
            TEAM2_EMOJIS[0]: [12],
            TEAM2_EMOJIS[1]: [11],
        }
    )
    votes = await _cog()._collect_votes(game, msg)
    assert votes[12] == {0: 11, 1: 21}
    assert votes[11] == {0: 12, 1: 22}


async def test_collect_votes_non_players_ignored():
    game = _game([11, 12], [21, 22])
    msg = _message({TEAM1_EMOJIS[0]: [99]})
    assert await _cog()._collect_votes(game, msg) == {}


async def test_collect_votes_bot_reactions_ignored():
    game = _game([11], [21])
    r = MagicMock()
    r.emoji = TEAM1_EMOJIS[0]
    r.users = MagicMock(return_value=_AsyncIter([_member(999, bot=True)]))
    msg = MagicMock()
    msg.reactions = [r]
    assert await _cog()._collect_votes(game, msg) == {}


async def test_collect_votes_partial_vote_one_team_only():
    game = _game([11, 12], [21, 22])
    msg = _message({TEAM1_EMOJIS[0]: [12]})
    assert await _cog()._collect_votes(game, msg) == {12: {0: 11}}


async def test_collect_votes_no_reactions():
    game = _game([11, 12], [21, 22])
    assert await _cog()._collect_votes(game, _message({})) == {}


async def test_collect_votes_multiple_voters_same_target():
    game = _game([11, 12], [21, 22])
    msg = _message({TEAM1_EMOJIS[0]: [11, 12]})
    votes = await _cog()._collect_votes(game, msg)
    assert votes[11][0] == 11
    assert votes[12][0] == 11


async def test_collect_votes_first_slot_wins_for_duplicate_team_votes():
    game = _game([11, 12], [21, 22])
    msg = _message({TEAM1_EMOJIS[0]: [12], TEAM1_EMOJIS[1]: [12]})
    assert await _cog()._collect_votes(game, msg) == {12: {0: 11}}


def test_weighted_sample_returns_exact_count():
    pop = [1, 2, 3, 4, 5]
    assert len(GameCog._weighted_sample(pop, {i: 1.0 for i in pop}, 3)) == 3


def test_weighted_sample_no_duplicates():
    pop = [1, 2, 3, 4, 5]
    result = GameCog._weighted_sample(pop, {i: 1.0 for i in pop}, 5)
    assert len(result) == len(set(result))


def test_weighted_sample_k_larger_than_population_capped():
    assert len(GameCog._weighted_sample([1, 2], {1: 1.0, 2: 1.0}, 100)) == 2


def test_weighted_sample_k_zero_returns_empty():
    assert GameCog._weighted_sample([1, 2, 3], {1: 1.0, 2: 1.0, 3: 1.0}, 0) == []


def test_weighted_sample_empty_population_returns_empty():
    assert GameCog._weighted_sample([], {}, 3) == []


def test_weighted_sample_skewed_weights_favour_heavy_player():
    selections = [GameCog._weighted_sample([1, 2], {1: 10_000.0, 2: 1.0}, 1)[0] for _ in range(200)]
    assert selections.count(1) > 180


def test_weighted_sample_only_draws_from_population():
    result = GameCog._weighted_sample([3, 4], {1: 99.0, 2: 99.0, 3: 1.0, 4: 1.0}, 2)
    assert set(result) <= {3, 4}


def test_player_limits_are_sane():
    assert MIN_PLAYERS_PER_TEAM >= 2
    assert MAX_PLAYERS_PER_TEAM <= 10
    assert MIN_PLAYERS_PER_TEAM < MAX_PLAYERS_PER_TEAM
