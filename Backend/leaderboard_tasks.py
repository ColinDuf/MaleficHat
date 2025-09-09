import asyncio
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from fonction_bdd import (
    get_all_players,
    get_all_guild_timezones,
    get_reset_timezone,
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

def _next_midnight(tz: ZoneInfo, now: datetime | None = None) -> datetime:
    """Return the next midnight for a timezone relative to ``now``."""
    now = datetime.now(tz) if now is None else now
    return datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=tz)


def _next_monday(tz: ZoneInfo, now: datetime | None = None) -> datetime:
    """Return the next Monday midnight for a timezone relative to ``now``."""
    now = datetime.now(tz) if now is None else now
    days_ahead = (0 - now.weekday() + 7) % 7 or 7
    next_monday_date = (now + timedelta(days=days_ahead)).date()
    return datetime.combine(next_monday_date, time.min, tzinfo=tz)


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

async def reset_lp_scheduler(bot):
    """Schedule LP resets per guild according to each timezone."""

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

    async def daily_reset(guild_id: int):
        while True:
            tz = ZoneInfo(get_reset_timezone(guild_id))
            target = _next_midnight(tz)
            while True:
                tz = ZoneInfo(get_reset_timezone(guild_id))
                now = datetime.now(tz)
                delta = (target - now).total_seconds()
                if delta <= 0:
                    break
                await asyncio.sleep(min(delta, 3600))
                target = _next_midnight(ZoneInfo(get_reset_timezone(guild_id)))
            if is_recap_enabled(guild_id, "daily"):
                await send_recap(guild_id, "daily")
            reset_lp_24h_for_guild(guild_id)
            leaderboard_update_event.set()

    async def weekly_reset(guild_id: int):
        while True:
            tz = ZoneInfo(get_reset_timezone(guild_id))
            target = _next_monday(tz)
            while True:
                tz = ZoneInfo(get_reset_timezone(guild_id))
                now = datetime.now(tz)
                delta = (target - now).total_seconds()
                if delta <= 0:
                    break
                await asyncio.sleep(min(delta, 3600))
                target = _next_monday(ZoneInfo(get_reset_timezone(guild_id)))
            if is_recap_enabled(guild_id, "weekly"):
                await send_recap(guild_id, "weekly")
            reset_lp_7d_for_guild(guild_id)
            leaderboard_update_event.set()

    scheduled: set[int] = set()

    async def ensure_tasks():
        while True:
            for guild_id, _ in get_all_guild_timezones():
                if guild_id not in scheduled:
                    bot.loop.create_task(daily_reset(guild_id))
                    bot.loop.create_task(weekly_reset(guild_id))
                    scheduled.add(guild_id)
            await asyncio.sleep(3600)

    bot.loop.create_task(ensure_tasks())
