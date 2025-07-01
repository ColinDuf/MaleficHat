import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch
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


def test_async_fetch_json_handles_timeout(bot_module):
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def raise_timeout(*args, **kwargs):
        raise asyncio.TimeoutError
        yield

    mock_session.get = raise_timeout

    with (
        patch('aiohttp.ClientSession', return_value=mock_session),
        patch('asyncio.sleep', new=AsyncMock()),
        patch.object(bot_module.logging, 'error') as log_error,
    ):
        result = asyncio.run(bot_module.async_fetch_json('http://example.com'))

    assert result is None
    log_error.assert_called_once()
