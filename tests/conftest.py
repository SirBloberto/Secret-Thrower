"""
Mock the database module before any test imports cogs, so tests never need
a live PostgreSQL or Redis connection.
"""
import sys
from unittest import mock

_mock_db = mock.MagicMock()
_mock_db.AsyncSessionLocal = mock.MagicMock()
_mock_db.redis_client = mock.MagicMock()
_mock_db.save_game_state = mock.AsyncMock()
_mock_db.load_game_state = mock.AsyncMock(return_value=None)
_mock_db.delete_game_state = mock.AsyncMock()
_mock_db.save_guild_settings = mock.AsyncMock()
_mock_db.load_guild_settings = mock.AsyncMock(return_value=None)

sys.modules["database"] = _mock_db
