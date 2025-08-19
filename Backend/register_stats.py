import logging
import discord

from fonction_bdd import count_players

ADMIN_CHANNEL_ID = 1388885265426415726

async def update_register_message(channel_id: int, bot: discord.Client):
    """Send or edit a table with registration and in-game stats."""
    registered_total = count_players()
    ingame_total = len(getattr(bot, "players_in_game", []))

    header1 = "Register"
    sep1 = "-" * len(header1)
    header2 = "Players in game"
    sep2 = "-" * len(header2)

    lines = [
        header1,
        sep1,
        str(registered_total),
        "",
        header2,
        sep2,
        str(ingame_total),
    ]
    table = "```" + "\n".join(lines) + "```"

    channel = bot.get_channel(channel_id)
    if channel is None:
        logging.error(
            f"[update_register_message] Channel with id {channel_id} not found"
        )
        return

    async for msg in channel.history(limit=50):
        if (
            msg.author == bot.user
            and msg.content.startswith("```")
            and header1 in msg.content
        ):
            await msg.edit(content=table)
            return

    try:
        await channel.send(table)
    except discord.DiscordException as e:
        logging.error(f"[update_register_message] Failed to send register stats: {e}")



