from constants import ELO_K, ELO_STARTING
from elo import EloUpdate, compute_elo_updates, k_factor

TEAM0 = [(1, False), (2, True)]
TEAM1 = [(3, False), (4, True)]
ROSTER = [TEAM0, TEAM1]

FRESH = {uid: (float(ELO_STARTING), float(ELO_STARTING)) for uid in (1, 2, 3, 4)}


def _thrower_elo(votes, winning_team_idx, user_id=2):
    return compute_elo_updates(ROSTER, votes, winning_team_idx, FRESH)[user_id].thrower_elo


def test_k_factor_at_baseline_equals_base_k():
    assert abs(k_factor(float(ELO_STARTING), 1.0) - ELO_K) < 0.01


def test_k_factor_gaining_is_easier_when_low():
    assert k_factor(20.0, 1.0) > k_factor(80.0, 1.0)


def test_k_factor_losing_is_harsher_when_high():
    assert k_factor(80.0, -1.0) > k_factor(20.0, -1.0)


def test_k_factor_always_positive():
    for elo in (0.0, 25.0, 50.0, 75.0, 100.0):
        assert k_factor(elo, 1.0) > 0
        assert k_factor(elo, -1.0) > 0


def test_every_player_gets_an_update():
    updates = compute_elo_updates(ROSTER, {}, 1, FRESH)
    assert set(updates) == {1, 2, 3, 4}
    assert all(isinstance(u, EloUpdate) for u in updates.values())


def test_clean_throw_is_the_best_thrower_outcome():
    clean = _thrower_elo({}, 1)
    caught_and_lost = _thrower_elo({1: {0: 2}}, 1)
    hidden_but_won = _thrower_elo({}, 0)
    caught_and_won = _thrower_elo({1: {0: 2}}, 0)

    assert clean > ELO_STARTING
    assert caught_and_lost < ELO_STARTING
    assert hidden_but_won < ELO_STARTING
    assert caught_and_won < ELO_STARTING
    assert clean > hidden_but_won > caught_and_lost > caught_and_won


def test_evaded_only_when_thrower_loses_unnoticed():
    assert compute_elo_updates(ROSTER, {}, 1, FRESH)[2].evaded is True
    assert compute_elo_updates(ROSTER, {1: {0: 2}}, 1, FRESH)[2].evaded is False
    assert compute_elo_updates(ROSTER, {}, 0, FRESH)[2].evaded is False


def test_innocent_gains_from_winning():
    updates = compute_elo_updates(ROSTER, {}, 0, FRESH)
    assert updates[1].innocent_elo > ELO_STARTING


def test_accurate_voter_beats_abstainer_on_the_same_team():
    roster = [[(1, False), (2, False), (3, True)], [(4, False), (5, True)]]
    ratings = {uid: (float(ELO_STARTING), float(ELO_STARTING)) for uid in range(1, 6)}
    updates = compute_elo_updates(roster, {1: {0: 3, 1: 5}}, 0, ratings)
    assert updates[1].innocent_elo > updates[2].innocent_elo


def test_thrower_only_affects_thrower_elo():
    update = compute_elo_updates(ROSTER, {}, 1, FRESH)[2]
    assert update.innocent_elo == float(ELO_STARTING)
    assert update.thrower_elo != float(ELO_STARTING)


def test_ratings_stay_within_bounds():
    extremes = {1: (0.0, 0.0), 2: (100.0, 100.0), 3: (0.0, 100.0), 4: (100.0, 0.0)}
    for votes in ({}, {1: {0: 2}, 3: {1: 4}}):
        for winner in (0, 1, None):
            for update in compute_elo_updates(ROSTER, votes, winner, extremes).values():
                assert 0.0 <= update.innocent_elo <= 100.0
                assert 0.0 <= update.thrower_elo <= 100.0


def test_unrated_players_start_from_the_baseline():
    known = compute_elo_updates(ROSTER, {}, 1, FRESH)
    unknown = compute_elo_updates(ROSTER, {}, 1, {})
    assert known == unknown


def test_is_pure():
    votes = {1: {0: 2, 1: 4}, 3: {0: 1}}
    first = compute_elo_updates(ROSTER, votes, 0, FRESH)
    second = compute_elo_updates(ROSTER, votes, 0, FRESH)
    assert first == second
    assert FRESH[1] == (float(ELO_STARTING), float(ELO_STARTING))


def test_no_winner_is_handled():
    updates = compute_elo_updates(ROSTER, {}, None, FRESH)
    assert set(updates) == {1, 2, 3, 4}
