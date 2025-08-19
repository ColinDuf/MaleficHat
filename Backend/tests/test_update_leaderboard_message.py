import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import asyncio
import pytest

@pytest.fixture(scope="module")
def leaderboard_module():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    if 'leaderboard' in sys.modules:
        del sys.modules['leaderboard']
    module = importlib.import_module('leaderboard')
    return module

def test_update_leaderboard_message_missing_channel(leaderboard_module):
    bot = MagicMock()
    guild = MagicMock()
    guild.get_channel.return_value = None
    bot.get_guild.return_value = guild

    with (
        patch.object(leaderboard_module, 'get_leaderboard_by_guild', return_value=1),
        patch.object(leaderboard_module, 'get_leaderboard_data', return_value=[]),
        patch.object(leaderboard_module, 'delete_leaderboard') as del_lb,
        patch.object(leaderboard_module.logging, 'info') as log_info,
    ):
        asyncio.run(leaderboard_module.update_leaderboard_message(123, bot, 456))
        del_lb.assert_called_once_with(456)
        log_info.assert_called_once_with(
            "[update_leaderboard_message] Dropped leaderboard for guild 456 because channel 123 is missing"
        )
