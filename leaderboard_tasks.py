import asyncio
from fonction_bdd import get_all_registrations
from leaderboard import update_leaderboard_embed

# Déclarez l'événement global pour signaler une mise à jour du leaderboard
leaderboard_update_event = asyncio.Event()

async def notify_leaderboard_update(bot):
    """
    Attend que l'événement soit déclenché pour mettre à jour le leaderboard dans tous les guilds concernés.
    """
    while True:
        await leaderboard_update_event.wait()
        leaderboard_update_event.clear()
        rows = get_all_registrations()
        # Récupère tous les guild_id uniques ayant un leaderboard
        guild_ids = {row[1] for row in rows}
        for guild_id in guild_ids:
            await update_leaderboard_embed(guild_id, bot)
        await asyncio.sleep(1)
