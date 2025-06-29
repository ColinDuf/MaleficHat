import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import pytest

@pytest.fixture(scope="module")
def bot_module():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    if 'bot' in sys.modules:
        del sys.modules['bot']
    with patch("discord.Client.run"):
        module = importlib.import_module('bot')
    module.discord_handler.emit = lambda *a, **k: None
    return module


def test_check_for_game_completion_handles_missing_row(bot_module):
    bot_module.players_in_game = {('puuid1', 1)}
    bot_module.players_in_game_messages = {('puuid1', 1): MagicMock()}
    bot_module.recent_match_lp_changes = {}

    async_get_all_players = AsyncMock(return_value=[])
    sleep_mock = AsyncMock(side_effect=asyncio.CancelledError)

    with (
        patch.object(bot_module, 'async_get_all_players', async_get_all_players),
        patch('asyncio.sleep', sleep_mock),
        patch.object(bot_module.register_stats, 'update_register_message', new=AsyncMock()),
    ):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(bot_module.check_for_game_completion())

    assert ('puuid1', 1) not in bot_module.players_in_game
    assert ('puuid1', 1) not in bot_module.players_in_game_messages
