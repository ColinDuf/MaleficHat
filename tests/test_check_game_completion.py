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


def test_check_for_game_completion_skips_flex_updates(bot_module):
    row = (
        'sid', 'puuid2', 'User', 1, 10, 'm1',
        'IV', 'GOLD', 50, 0, 0, 'euw1', 1
    )
    bot_module.players_in_game = {('puuid2', 1)}
    bot_module.players_in_game_messages = {('puuid2', 1): MagicMock()}
    bot_module.recent_match_lp_changes = {}

    with (
        patch.object(bot_module, 'async_get_all_players', AsyncMock(return_value=[row])),
        patch.object(bot_module, 'async_is_in_game', AsyncMock(return_value=False)),
        patch.object(bot_module, 'async_get_last_match', AsyncMock(return_value=['m2'])),
        patch.object(bot_module, 'async_get_match_details', AsyncMock(return_value=(
            ':green_circle:', 'Champ', 1, 2, 3, 1800, 'img', 1000, False
        ))),
        patch.object(bot_module, 'get_summoner_rank_details_by_puuid', AsyncMock(return_value={
            'tier': 'GOLD', 'rank': 'IV', 'lp': 50
        })),
        patch.object(bot_module, 'send_match_result_embed', AsyncMock()),
        patch.object(bot_module.leaderboard, 'update_leaderboard_message') as upd_lb,
        patch.object(bot_module, 'update_player_global') as upd_global,
        patch('asyncio.sleep', AsyncMock(side_effect=asyncio.CancelledError)),
        patch.object(bot_module.register_stats, 'update_register_message', new=AsyncMock()),
    ):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(bot_module.check_for_game_completion())

    upd_global.assert_not_called()
    upd_lb.assert_not_called()
