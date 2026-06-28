"""Tests for Game serialisation — no Discord or DB needed."""
from data import Game, GameSettings, GameState


def _make_game() -> Game:
    game = Game(guild_id=111222333)
    game.game_id = 999888777
    game.state = GameState.PLAYING
    game.thrower_ids = [10, 20]
    game.winning_channel_id = 555
    game.vote_end_timestamp = 1700000000
    game.host_id = 42
    game.text_channel_id = 77
    game.settings = GameSettings(voting_timer=90, thrower_info=True)
    # team1/team2/message are None — re-attached from Discord on recovery
    return game


def test_round_trip_preserves_all_metadata():
    game = _make_game()
    restored = Game.from_json(game.to_json())

    assert restored.guild_id == game.guild_id
    assert restored.game_id == game.game_id
    assert restored.state == game.state
    assert restored.thrower_ids == game.thrower_ids
    assert restored.winning_channel_id == game.winning_channel_id
    assert restored.vote_end_timestamp == game.vote_end_timestamp
    assert restored.host_id == game.host_id
    assert restored.text_channel_id == game.text_channel_id
    assert restored.settings.voting_timer == game.settings.voting_timer
    assert restored.settings.thrower_info == game.settings.thrower_info


def test_round_trip_with_no_optional_fields():
    game = Game(guild_id=1)
    restored = Game.from_json(game.to_json())

    assert restored.guild_id == 1
    assert restored.game_id is None
    assert restored.state == GameState.SETUP
    assert restored.thrower_ids == []
    assert restored.winning_channel_id is None
    assert restored.vote_end_timestamp is None
    assert restored.host_id is None
    assert restored.text_channel_id is None


def test_teams_are_none_after_deserialisation():
    """Teams are Discord objects; from_json intentionally leaves them as None."""
    game = _make_game()
    restored = Game.from_json(game.to_json())
    assert restored.team1 is None
    assert restored.team2 is None


def test_get_teams_with_none_teams():
    game = Game(guild_id=1)
    assert game.get_teams() == [None, None]
