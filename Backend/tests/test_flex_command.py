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
    interaction.guild.name = "Guild One"
    interaction.response.send_message = AsyncMock()

    with (
        patch.object(bot_module, 'insert_guild') as ins_guild,
    ):
        asyncio.run(bot_module.flex.callback(interaction, 'enable'))

    ins_guild.assert_called_once_with(1, flex_enabled=1, name="Guild One")
    interaction.response.send_message.assert_awaited_once()


def test_flex_command_disable(bot_module):
    interaction = MagicMock()
    interaction.guild.id = 2
    interaction.guild.name = "Guild Two"
    interaction.response.send_message = AsyncMock()

    with patch.object(bot_module, 'insert_guild') as ins_guild:
        asyncio.run(bot_module.flex.callback(interaction, 'disable'))

    ins_guild.assert_called_once_with(2, flex_enabled=0, name="Guild Two")
    interaction.response.send_message.assert_awaited_once()
