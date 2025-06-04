import asyncio
from datetime import datetime, date, time, timedelta
from fonction_bdd import get_all_players, reset_all_lp_24h, reset_all_lp_7d
from leaderboard import update_leaderboard_message

leaderboard_update_event = asyncio.Event()

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
    """
    Lance deux coroutines :
     - daily at 00:00 → reset lp_24h
     - every Monday at 00:00 → reset lp_7d
    Et déclenche leaderboard_update_event à chaque reset.
    """
    async def wait_until(target: datetime):
        now = datetime.now()
        delta = (target - now).total_seconds()
        if delta > 0:
            await asyncio.sleep(delta)

    async def daily_reset():
        while True:
            today = date.today()
            next_midnight = datetime.combine(today + timedelta(days=1), time.min)
            await wait_until(next_midnight)

            reset_all_lp_24h()
            leaderboard_update_event.set()

    async def weekly_reset():
        while True:
            today = date.today()
            days_ahead = (0 - today.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            next_monday = datetime.combine(today + timedelta(days=days_ahead), time.min)
            await wait_until(next_monday)

            reset_all_lp_7d()
            leaderboard_update_event.set()

    bot.loop.create_task(daily_reset())
    bot.loop.create_task(weekly_reset())