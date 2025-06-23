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
    with patch("discord.Client.run"):
        module = importlib.import_module('bot')
    module.discord_handler.emit = lambda *a, **k: None
    return module

@pytest.mark.parametrize("title", ["Victory for Player", "Player is playing a game!"])
def test_handle_music_reaction(bot_module, title):
    payload = SimpleNamespace(
        emoji='🎉',
        guild_id=1,
        channel_id=2,
        message_id=3,
        user_id=4,
    )

    member = MagicMock(bot=False)
    member.voice = MagicMock(channel=MagicMock())
    guild = MagicMock()
    guild.fetch_member = AsyncMock(return_value=member)
    guild.get_channel.return_value = MagicMock()
    guild.get_channel.return_value.fetch_message = AsyncMock(return_value=MagicMock(
        author=bot_module.client.user,
        embeds=[MagicMock(title=title)]
    ))
    guild.voice_client = None

    voice_client = MagicMock()
    member.voice.channel.connect = AsyncMock(return_value=voice_client)
    voice_client.is_playing.side_effect = [True, False]
    voice_client.disconnect = AsyncMock()

    with (
        patch.object(bot_module.client, 'get_guild', return_value=guild),
        patch.object(Path, 'exists', return_value=True),
        patch('discord.FFmpegPCMAudio'),
        patch('asyncio.sleep', new_callable=AsyncMock),
    ):
        asyncio.run(bot_module.handle_music_reaction(payload))

    member.voice.channel.connect.assert_called_once()
    voice_client.play.assert_called_once()
    voice_client.disconnect.assert_called_once()
