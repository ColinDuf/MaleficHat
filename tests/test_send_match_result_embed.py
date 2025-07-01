import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch
import asyncio
import discord
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


def test_send_match_result_embed_early_surrender(bot_module):
    channel = AsyncMock()
    asyncio.run(
        bot_module.send_match_result_embed(
            channel,
            'Player',
            ':red_circle:',
            1,
            2,
            3,
            'http://image',
            -10,
            1000,
            True,
        )
    )

    channel.send.assert_awaited_once()
    embed = channel.send.call_args.kwargs['embed']
    assert embed.title == 'Early Surrender for Player'
    assert embed.color.value == discord.Color.orange().value
