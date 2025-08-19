import importlib
import sys
from types import SimpleNamespace
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
    with patch('discord.Client.run'):
        module = importlib.import_module('bot')
    module.discord_handler.emit = lambda *a, **k: None
    return module


def test_handle_spectate_reaction(bot_module):
    payload = SimpleNamespace(
        emoji='📽️',
        guild_id=1,
        channel_id=2,
        message_id=3,
        user_id=4,
    )

    message = MagicMock(id=3)
    message.author = bot_module.client.user
    message.embeds = [MagicMock(title="Player is playing a game!")]

    guild = MagicMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    channel.send = AsyncMock()
    guild.get_channel.return_value = channel
    guild.fetch_member = AsyncMock(return_value=MagicMock())

    bot_module.players_in_game_messages = {('puuid', 1): message}

    with (
        patch.object(bot_module.client, 'get_guild', return_value=guild),
        patch.object(bot_module, 'get_player', return_value=(
            'sid','puuid','Player',1,2,'m1','IV','GOLD',50,0,0,'euw1','IV','GOLD',50
        )),
        patch.object(bot_module, 'async_fetch_json', AsyncMock(return_value={
            'observers': {'encryptionKey': 'key'},
            'gameId': '123',
            'platformId': 'EUW1'
        })),
    ):
        asyncio.run(bot_module.handle_spectate_reaction(payload))

    channel.send.assert_awaited_once()
