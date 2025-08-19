import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import pytest

@pytest.fixture(scope="module")
def register_module():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    if 'register_stats' in sys.modules:
        del sys.modules['register_stats']
    module = importlib.import_module('register_stats')
    return module


def test_update_register_message_missing_channel(register_module):
    bot = MagicMock()
    bot.get_channel.return_value = None

    with (
        patch.object(register_module.logging, 'error') as log_error,
        patch.object(register_module, 'count_players', return_value=5)
    ):
        asyncio.run(register_module.update_register_message(123, bot))
        log_error.assert_called_once_with(
            '[update_register_message] Channel with id 123 not found'
        )


def test_update_register_message_updates_existing(register_module):
    bot = MagicMock()
    bot.user = object()
    bot.players_in_game = {('p', 1)}

    msg = MagicMock()
    msg.author = bot.user
    msg.content = '```Register\n--------\n1```'
    msg.edit = AsyncMock()

    async def history(limit=50):
        yield msg

    channel = MagicMock()
    channel.history.side_effect = history
    bot.get_channel.return_value = channel

    expected_lines = [
        'Register',
        '--------',
        '5',
        '',
        'Players in game',
        '---------------',
        '1',
    ]
    expected_table = '```' + '\n'.join(expected_lines) + '```'

    with (
        patch.object(register_module, 'count_players', return_value=5),
    ):
        asyncio.run(register_module.update_register_message(1, bot))

    msg.edit.assert_awaited_once_with(content=expected_table)

