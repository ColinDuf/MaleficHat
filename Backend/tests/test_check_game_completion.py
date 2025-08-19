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
    ):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(bot_module.check_for_game_completion())

    assert ('puuid1', 1) not in bot_module.players_in_game
    assert ('puuid1', 1) not in bot_module.players_in_game_messages


def test_check_for_game_completion_updates_flex_rank(bot_module):
    bot_module.players_in_game = {('p1', 1)}
    bot_module.players_in_game_messages = {}
    bot_module.recent_match_lp_changes = {}

    row = (
        'p1', 'USER#TAG', 1, 123, 'm0',
        'IV', 'GOLD', 50, 0, 0,
        'III', 'SILVER', 20
    )

    async_get_all_players = AsyncMock(return_value=[row])
    async_is_in_game = AsyncMock(return_value=False)
    async_get_last_match = AsyncMock(return_value=['m1'])
    async_fetch_json = AsyncMock(return_value={'info': {'queueId': 440, 'participants': [{'gameEndedInEarlySurrender': False}]}})
    async_get_match_details = AsyncMock(return_value=('Win', 'Ahri', 10, 2, 5, '30:00', 'img', 1000))
    get_rank_details = MagicMock(return_value={'tier': 'SILVER', 'rank': 'II', 'lp': 40})
    calc_lp_change = MagicMock(return_value=10)
    update_player_global = MagicMock()
    update_player_guild = MagicMock()
    send_match_result_embed = AsyncMock()
    leaderboard_update = AsyncMock()

    with (
        patch.object(bot_module, 'async_get_all_players', async_get_all_players),
        patch.object(bot_module, 'async_is_in_game', async_is_in_game),
        patch.object(bot_module, 'async_get_last_match', async_get_last_match),
        patch.object(bot_module, 'async_fetch_json', async_fetch_json),
        patch.object(bot_module, 'async_get_match_details', async_get_match_details),
        patch.object(bot_module, 'get_summoner_rank_details_by_puuid', get_rank_details),
        patch.object(bot_module, 'calculate_lp_change', calc_lp_change),
        patch.object(bot_module, 'update_player_global', update_player_global),
        patch.object(bot_module, 'update_player_guild', update_player_guild),
        patch.object(bot_module, 'send_match_result_embed', send_match_result_embed),
        patch.object(bot_module.leaderboard, 'update_leaderboard_message', leaderboard_update),
        patch.object(bot_module, 'get_guild', return_value=(1, 456, 1)),
        patch('asyncio.sleep', AsyncMock(side_effect=asyncio.CancelledError)),
    ):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(bot_module.check_for_game_completion())

    async_is_in_game.assert_awaited_once_with('p1', True)
    update_player_global.assert_called_once_with(
        'p1',
        flex_tier='II',
        flex_rank='SILVER',
        flex_lp=40,
        lp_change=10
    )
