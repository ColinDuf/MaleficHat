import asyncio
from unittest.mock import AsyncMock, MagicMock
from test_flex_command import bot_module


def test_howtosetup_command(bot_module):
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()

    asyncio.run(bot_module.howtosetup_cmd.callback(interaction))

    interaction.response.send_message.assert_awaited_once_with(
        (
            "To set up the bot: /leaderboard creates a leaderboard channel, "
            "/register adds players, /settime chooses your reset timezone, "
            "/recap daily|weekly enable enables recap messages. For more help join "
            "https://discord.gg/vZHPkBHmkC"
        ),
        ephemeral=True,
    )
