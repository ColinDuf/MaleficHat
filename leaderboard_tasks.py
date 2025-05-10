import asyncio
from fonction_bdd import get_all_players
from leaderboard import update_leaderboard_embed

leaderboard_update_event = asyncio.Event()

async def notify_leaderboard_update(bot):
    """
    Attend que l'événement soit déclenché pour mettre à jour le leaderboard dans tous les guilds concernés.
    """
    while True:
        await leaderboard_update_event.wait()
        leaderboard_update_event.clear()
        players = get_all_players()
        # Extraire tous les guild_id uniques depuis les joueurs enregistrés
        guild_ids = {player[3] for player in players}  # index 3 correspond à guild_id dans le tuple retourné
        for guild_id in guild_ids:
            # On récupère le leaderboard_channel_id à partir de la table guild via get_guild dans update_leaderboard_embed
            await update_leaderboard_embed(guild_id, bot)
        await asyncio.sleep(1)
