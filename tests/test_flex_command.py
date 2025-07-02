import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio
import pytest

@pytest.fixture(scope="module")
def bot_module():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    if 'bot' in sys.modules:
        del sys.modules['bot']
    with patch('discord.Client.run'):
        module = importlib.import_module('bot')
    module.discord_handler.emit = lambda *a, **k: None
    return module


def test_flex_command_enable(bot_module):
    interaction = MagicMock()
    interaction.guild.id = 1
    interaction.response.send_message = AsyncMock()

    with (
        patch.object(bot_module, 'get_guild', return_value=None),
        patch.object(bot_module, 'insert_guild') as ins_guild,
        patch.object(bot_module, 'set_guild_flex_mode') as set_flex,
    ):
        asyncio.run(bot_module.flex.callback(interaction, 'on'))

    ins_guild.assert_called_once_with(1, None, 1)
    set_flex.assert_not_called()
    interaction.response.send_message.assert_awaited_once()


def test_flex_command_disable(bot_module):
    interaction = MagicMock()
    interaction.guild.id = 2
    interaction.response.send_message = AsyncMock()

    with (
        patch.object(bot_module, 'get_guild', return_value=(2, None, 1)),
        patch.object(bot_module, 'set_guild_flex_mode') as set_flex,
    ):
        asyncio.run(bot_module.flex.callback(interaction, 'off'))

    set_flex.assert_called_once_with(2, False)
    interaction.response.send_message.assert_awaited_once()

