import asyncio
from datetime import datetime, time, timedelta
import pytz
from fonction_bdd import (
    get_all_players,
    get_all_guild_ids,
    reset_lp_24h_for_guild,
    reset_lp_7d_for_guild,
    is_recap_enabled,
    get_guild,
    get_leaderboard_by_guild,
    get_leaderboard_data,
)
from leaderboard import update_leaderboard_message
from recap import build_recap_embed

leaderboard_update_event = asyncio.Event()
PARIS_TZ = pytz.timezone("Europe/Paris")

def _next_midnight(now: datetime | None = None) -> datetime:
    """Return the next midnight Europe/Paris (timezone-aware)."""
    now_paris = datetime.now(PARIS_TZ) if now is None else now.astimezone(PARIS_TZ)
    tomorrow = (now_paris + timedelta(days=1)).date()
    return PARIS_TZ.localize(datetime.combine(tomorrow, time.min))


def _next_monday(now: datetime | None = None) -> datetime:
    """Return the next Monday 00:00 Europe/Paris (timezone-aware)."""
    now_paris = datetime.now(PARIS_TZ) if now is None else now.astimezone(PARIS_TZ)
    days_ahead = (0 - now_paris.weekday() + 7) % 7 or 7
    next_monday_date = (now_paris + timedelta(days=days_ahead)).date()
    return PARIS_TZ.localize(datetime.combine(next_monday_date, time.min))


async def notify_leaderboard_update(bot):
    """
    Attend que l'événement soit déclenché pour mettre à jour le leaderboard dans tous les guilds concernés.
    """
    while True:
        await leaderboard_update_event.wait()
        leaderboard_update_event.clear()
        players = get_all_players()
        guild_ids = {player[3] for player in players}
        for guild_id in guild_ids:
            await update_leaderboard_message(guild_id, bot)
        await asyncio.sleep(1)

async def run_leaderboard_update_pump(bot):
    """Background task: when an update event is set, refresh leaderboards
    for all guilds that have a leaderboard channel configured."""
    while True:
        await leaderboard_update_event.wait()
        leaderboard_update_event.clear()

        for guild_id in get_all_guild_ids():
            guild_row = get_guild(guild_id)
            if not guild_row:
                continue
            channel_id = guild_row[1]
            if channel_id is None:
                continue
            await update_leaderboard_message(channel_id, bot, guild_id)

        await asyncio.sleep(1)

async def reset_lp_scheduler(bot):
    """Schedule LP resets for all guilds using Europe/Paris timezone."""

    async def send_recap(guild_id: int, period: str):
        lb_id = get_leaderboard_by_guild(guild_id)
        if lb_id is None:
            return
        rows = get_leaderboard_data(lb_id, guild_id)
        if not rows:
            return
        guild_row = get_guild(guild_id)
        if not guild_row:
            return
        channel_id = guild_row[1]
        if channel_id is None:
            return
        channel = bot.get_channel(channel_id)
        if channel is None:
            return
        embed = build_recap_embed(rows, period)
        if embed.fields:
            await channel.send(embed=embed)

    async def daily_reset():
        while True:
            target = _next_midnight()
            while True:
                now = datetime.now(PARIS_TZ)
                delta = (target - now).total_seconds()
                if delta <= 0:
                    break
                await asyncio.sleep(min(delta, 3600))
            for guild_id in get_all_guild_ids():
                if is_recap_enabled(guild_id, "daily"):
                    await send_recap(guild_id, "daily")
                reset_lp_24h_for_guild(guild_id)
            leaderboard_update_event.set()

    async def weekly_reset():
        while True:
            target = _next_monday()
            while True:
                now = datetime.now(PARIS_TZ)
                delta = (target - now).total_seconds()
                if delta <= 0:
                    break
                await asyncio.sleep(min(delta, 3600))
            for guild_id in get_all_guild_ids():
                if is_recap_enabled(guild_id, "weekly"):
                    await send_recap(guild_id, "weekly")
                reset_lp_7d_for_guild(guild_id)
            leaderboard_update_event.set()

    bot.loop.create_task(daily_reset())
    bot.loop.create_task(weekly_reset())
