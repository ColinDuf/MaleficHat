import asyncio
from unittest.mock import AsyncMock, MagicMock
from test_flex_command import bot_module


def test_help_command(bot_module):
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()

    asyncio.run(bot_module.help_cmd.callback(interaction))

    interaction.response.send_message.assert_awaited_once_with(
        "Need help? Join our support server: https://discord.gg/vZHPkBHmkC",
        ephemeral=True,
    )
