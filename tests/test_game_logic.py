"""Tests for pure game-logic static methods — no Discord or DB needed."""
import pytest

from cogs.game import GameCog


# ---------------------------------------------------------------------------
# _weighted_sample
# ---------------------------------------------------------------------------


def test_weighted_sample_returns_exact_count():
    pop = [1, 2, 3, 4, 5]
    weights = {i: 1.0 for i in pop}
    result = GameCog._weighted_sample(pop, weights, 3)
    assert len(result) == 3


def test_weighted_sample_no_duplicates():
    pop = [1, 2, 3, 4, 5]
    weights = {i: 1.0 for i in pop}
    result = GameCog._weighted_sample(pop, weights, 5)
    assert len(result) == len(set(result))


def test_weighted_sample_k_larger_than_population_capped():
    pop = [1, 2]
    weights = {1: 1.0, 2: 1.0}
    result = GameCog._weighted_sample(pop, weights, 100)
    assert len(result) == 2


def test_weighted_sample_k_zero_returns_empty():
    pop = [1, 2, 3]
    weights = {i: 1.0 for i in pop}
    result = GameCog._weighted_sample(pop, weights, 0)
    assert result == []


def test_weighted_sample_empty_population_returns_empty():
    result = GameCog._weighted_sample([], {}, 3)
    assert result == []


def test_weighted_sample_skewed_weights_favour_heavy_player():
    """Player 1 has 10 000× more weight; they should be selected nearly every time."""
    pop = [1, 2]
    weights = {1: 10_000.0, 2: 1.0}
    selections = [GameCog._weighted_sample(pop, weights, 1)[0] for _ in range(200)]
    assert selections.count(1) > 180


def test_weighted_sample_only_draws_from_population():
    pop = [3, 4]
    weights = {1: 99.0, 2: 99.0, 3: 1.0, 4: 1.0}
    result = GameCog._weighted_sample(pop, weights, 2)
    assert set(result) <= set(pop)


# ---------------------------------------------------------------------------
# ELO constants sanity
# ---------------------------------------------------------------------------


def test_elo_k_is_positive():
    from constants import ELO_K, ELO_STARTING
    assert ELO_K > 0
    assert ELO_STARTING > 0


def test_player_limits_are_sane():
    from constants import MAX_PLAYERS_PER_TEAM, MIN_PLAYERS_PER_TEAM
    assert MIN_PLAYERS_PER_TEAM >= 2
    assert MAX_PLAYERS_PER_TEAM <= 10
    assert MIN_PLAYERS_PER_TEAM < MAX_PLAYERS_PER_TEAM
