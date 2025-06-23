import aiohttp
import discord
from discord import app_commands
import os
import logging
import asyncio
from datetime import timedelta
from dotenv import load_dotenv
from create_db import create_db
from leaderboard_tasks import reset_lp_scheduler
import leaderboard
from fonction_bdd import (insert_player, get_player_by_username, delete_player,
                          username_autocomplete, get_player, get_all_players,
                          get_guild, insert_guild, insert_player_guild,
                          update_player_guild, update_player_global,
                          get_leaderboard_by_guild, delete_leaderboard_member,
                          count_players)
import requests
import tracemalloc
from pathlib import Path
from log import DiscordLogHandler
import time

tracemalloc.start()
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'
)

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', '').strip()
RIOT_API_KEY = os.getenv('RIOT_API_KEY', '').strip()

discord_logger = logging.getLogger("discord")
discord_logger.setLevel(logging.WARNING)
for noisy in ("discord.voice_client", "discord.voice_state", "discord.player"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
leaderboard.setup_tree(tree)

DISCORD_LOG_CHANNEL_ID = 1379139184635154442
discord_handler = DiscordLogHandler(client, DISCORD_LOG_CHANNEL_ID)
discord_handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'
)
discord_handler.setFormatter(formatter)
logging.getLogger().addHandler(discord_handler)

players_in_game: set[tuple[str, int]] = set()
players_in_game_messages: dict[tuple[str, int], discord.Message] = {}
CHAMPION_MAPPING: dict[int, str] = {}
recent_match_lp_changes: dict[tuple[str, str], tuple[int, float]] = {}

MATCH_CACHE_EXPIRATION = 3600  # seconds

RETRY_STATUS_CODES = {502, 503, 504}

# Mapping from reaction emoji to local music file
MUSIC_REACTIONS = {
    "🎉": Path("music/kiffance.mp3"),
    "🎺": Path("music/ole.mp3"),
}


def fetch_json(url: str, headers: dict | None = None,
               retries: int = 3, backoff: float = 1.0):
    """GET JSON data with simple retry logic for 5xx errors."""
    if headers:
        headers = {str(k): str(v) for k, v in headers.items()
                   if k is not None and v is not None}

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code in RETRY_STATUS_CODES:
                raise requests.exceptions.HTTPError(f"{resp.status_code}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            if attempt == retries:
                logging.error(f"Error fetching {url}: {e}")
                return None
            time.sleep(backoff * attempt)


async def async_fetch_json(url: str, headers: dict | None = None,
                           retries: int = 3, backoff: float = 1.0):
    if headers:
        headers = {str(k): str(v) for k, v in headers.items()
                   if k is not None and v is not None}

    for attempt in range(1, retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status in RETRY_STATUS_CODES:
                        raise aiohttp.ClientResponseError(resp.request_info, resp.history, status=resp.status)
                    if resp.status == 404:
                        return None
                    resp.raise_for_status()
                    return await resp.json()
        except aiohttp.ClientError as e:
            if attempt == retries:
                logging.error(f"Error fetching {url}: {e}")
                return None
            await asyncio.sleep(backoff * attempt)

##############################################################################
# Fonctions d'accès à l'API Riot (appel synchrones via requests)
##############################################################################

def get_puuid(username, hashtag):
    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{username}/{hashtag}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    data = fetch_json(url, headers=headers)
    return data.get('puuid') if data else None

def get_summoner_id(puuid):
    url = f"https://euw1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    data = fetch_json(url, headers=headers)
    return data.get('id') if data else None

def get_summoner_rank_details(summoner_id: str):
    """Return detailed solo/duo rank info for a summoner ID."""
    url = (
        "https://euw1.api.riotgames.com/lol/league/v4/entries/by-summoner/"
        f"{summoner_id}"
    )
    headers = {"X-Riot-Token": RIOT_API_KEY}
    data = fetch_json(url, headers=headers)
    if isinstance(data, list):
        for entry in data:
            if entry.get("queueType") == "RANKED_SOLO_5x5":
                return {
                    "tier": entry.get("tier"),
                    "rank": entry.get("rank"),
                    "lp": entry.get("leaguePoints"),
                    "wins": entry.get("wins"),
                    "losses": entry.get("losses"),
                }
    return None


def get_summoner_rank_details_by_puuid(puuid: str):
    """Return detailed solo/duo rank info using the PUUID directly."""
    url = (
        "https://euw1.api.riotgames.com/lol/league/v4/entries/by-puuid/"
        f"{puuid}"
    )
    headers = {"X-Riot-Token": RIOT_API_KEY}
    data = fetch_json(url, headers=headers)
    if isinstance(data, list):
        for entry in data:
            if entry.get("queueType") == "RANKED_SOLO_5x5":
                return {
                    "tier": entry.get("tier"),
                    "rank": entry.get("rank"),
                    "lp": entry.get("leaguePoints"),
                    "wins": entry.get("wins"),
                    "losses": entry.get("losses"),
                }
    return None

def get_summoner_rank(summoner_id):
    details = get_summoner_rank_details(summoner_id)
    if details:
        return f"{details['tier']} {details['rank']} {details['lp']} LP"
    return "Unknown"

def get_last_match(puuid, nb_last_match):
    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?type=ranked&count={nb_last_match}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    matches = fetch_json(url, headers=headers)
    if isinstance(matches, list) and matches:
        return matches
    return None


def get_ddragon_latest_version() -> str:
    """
    Récupère la liste des versions Data Dragon depuis Riot,
    et retourne la première (la plus récente)".
    """
    versions_url = "https://ddragon.leagueoflegends.com/api/versions.json"
    versions = fetch_json(versions_url)
    if isinstance(versions, list) and versions:
        return versions[0]
    logging.error("Failed to retrieve Data Dragon version: unexpected response.")
    return "25.11"


def init_champion_mapping() -> None:
    """
    Utilise get_ddragon_latest_version() pour récupérer la dernière version,
    puis charge le champ 'champion.json' correspondant, afin de remplir
    CHAMPION_MAPPING = { int(key) : name } pour chaque champion.
    """
    global CHAMPION_MAPPING
    version = get_ddragon_latest_version()

    url_champs = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    resp = fetch_json(url_champs)
    data = resp.get("data", {}) if isinstance(resp, dict) else {}

    CHAMPION_MAPPING.clear()
    for champ_name, champ_info in data.items():
        try:
            champ_id_int = int(champ_info["key"])
            CHAMPION_MAPPING[champ_id_int] = champ_info["id"]
        except Exception:
            continue


def get_match_details(match_id: str, puuid: str):
    """
    Récupère les détails d'un match classé (.match/v5) pour un joueur donné (par son PUUID).
    Construit aussi l’URL de l’image du champion en utilisant la version Data Dragon la plus récente.
    """
    if not match_id:
        logging.error("No match ID provided.")
        return None

    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    match_data = fetch_json(url, headers=headers)
    if not match_data:
        return None
    game_mode = match_data.get("info", {}).get("queueId")
    if game_mode == 420:
        # Récupère la version Data Dragon à la volée
        ddragon_version = get_ddragon_latest_version()

        for participant in match_data["info"].get("participants", []):
            if participant.get("puuid") == puuid:
                # Résultat (victoire/défaite)
                result = ":green_circle:" if participant.get("win") else ":red_circle:"
                champion = participant.get("championName", "")
                champ_id = participant.get("championId")
                kills = participant.get("kills", 0)
                deaths = participant.get("deaths", 0)
                assists = participant.get("assists", 0)
                damage = participant.get("totalDamageDealtToChampions", 0)

                # Durée de la partie (format mm:ss ou hh:mm:ss)
                game_duration_seconds = match_data["info"].get("gameDuration", 0)
                if game_duration_seconds >= 3600:
                    game_duration = str(timedelta(seconds=game_duration_seconds))
                else:
                    minutes = game_duration_seconds // 60
                    seconds = game_duration_seconds % 60
                    game_duration = f"{minutes}:{seconds:02d}"

                champ_slug = CHAMPION_MAPPING.get(champ_id, champion)
                champion_image = (
                    f"https://ddragon.leagueoflegends.com/cdn/"
                    f"{ddragon_version}/img/champion/{champ_slug}.png"
                )

                return (
                    result,
                    champion,
                    kills,
                    deaths,
                    assists,
                    game_duration,
                    champion_image,
                    damage
                )

    return None


async def check_username_changes():
    """
    Tâche quotidienne : vérifie si un joueur a changé de username.
    """
    while True:
        players = await async_get_all_players()
        for player in players:
            summoner_id, puuid, old_username, *_ = player

            url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
            headers = {"X-Riot-Token": RIOT_API_KEY}
            data = await async_fetch_json(url, headers=headers)
            if data:
                current_username = (
                        data.get("gameName", "").upper() + "#" + data.get("tagLine", "").upper()
                )
                if current_username != old_username:
                    update_player_global(puuid, username=current_username)
                    logging.info(
                        f"Username updated: {old_username} -> {current_username}"
                    )
            else:
                logging.warning(
                    f"❌ Riot API error for PUUID {puuid}"
                )

        await asyncio.sleep(86400)


def calculate_lp_change(old_tier, old_rank, old_lp, new_tier, new_rank, new_lp):

    rank_order = [
        'IRON', 'BRONZE', 'SILVER', 'GOLD',
        'PLATINUM', 'EMERALD', 'DIAMOND',
        'MASTER', 'GRANDMASTER', 'CHALLENGER'
    ]
    tier_order = ['IV', 'III', 'II', 'I']

    try:
        # Cas où la catégorie (rank) n'a pas changé
        if old_rank == new_rank:
            # Rangs sans divisions (Master et au-dessus)
            if old_rank in {"MASTER", "GRANDMASTER", "CHALLENGER"}:
                return new_lp - old_lp

            # Même division → on renvoie juste la différence de LP
            if old_tier == new_tier:
                return new_lp - old_lp

            # Même catégorie, division différente
            tier_diff = (tier_order.index(new_tier) - tier_order.index(old_tier)) * 100
            return tier_diff + (new_lp - old_lp)

        # Promotion vers les rangs sans division
        if new_rank == "MASTER" and old_rank == "DIAMOND":
            return 100 - old_lp
        if new_rank == "GRANDMASTER" and old_rank == "MASTER":
            return 200 - old_lp
        if new_rank == "CHALLENGER" and old_rank == "GRANDMASTER":
            return 200 - old_lp

        # Changement de catégorie (rank) standard
        rank_diff = (rank_order.index(new_rank) - rank_order.index(old_rank)) * 400
        old_tier_idx = tier_order.index(old_tier) if old_tier in tier_order else 0
        new_tier_idx = tier_order.index(new_tier) if new_tier in tier_order else 0
        tier_diff = (new_tier_idx - old_tier_idx) * 100
        return rank_diff + tier_diff + (new_lp - old_lp)

    except ValueError as e:
        logging.error(f"[LP ERROR] Invalid tier/rank value: {e}")
        return 0


async def is_in_game(puuid: str) -> int | None:
    """
    Si le joueur est en ranked solo/duo (queue 420), renvoie son championId (int).
    Sinon renvoie None.
    """
    url = f"https://euw1.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
    headers = {"X-Riot-Token": RIOT_API_KEY}

    data = await async_fetch_json(url, headers=headers)
    if not data:
        return None
    if data.get("gameQueueConfigId") != 420:
        return None
    for participant in data.get("participants", []):
        if participant.get("puuid") == puuid:
            return participant.get("championId")
    return None


###############################################################################
# Wrappers asynchrones pour les appels bloquants
###############################################################################
async def async_get_all_players():
    return await asyncio.to_thread(get_all_players)

async def async_is_in_game(puuid):
    return await is_in_game(puuid)

async def async_get_last_match(puuid, nb_last_match):
    return await asyncio.to_thread(get_last_match, puuid, nb_last_match)

async def async_get_match_details(match_id, puuid):
    return await asyncio.to_thread(get_match_details, match_id, puuid)


###############################################################################
# Commandes (register, unregister, rank, career)
###############################################################################

@tree.command(
    name="register",
    description="Register a player in this server and activate alert"
)
@app_commands.describe(
    gamename="The player's Riot in game name",
    tagline="The player's #"
)
async def register(interaction: discord.Interaction, gamename: str, tagline: str):
    await interaction.response.defer(ephemeral=True)
    username = f"{gamename.upper()}#{tagline.upper()}"
    try:
        riot_username, hashtag = username.split("#")
    except ValueError:
        return await interaction.followup.send(
            "Invalid username format. Use USERNAME#HASHTAG.",
            ephemeral=True
        )

    puuid = await asyncio.to_thread(get_puuid, riot_username, hashtag)
    if not puuid:
        return await interaction.followup.send(
            f"Error fetching PUUID for {username}.", ephemeral=True
        )
    summoner_id = await asyncio.to_thread(get_summoner_id, puuid)
    if not summoner_id:
        return await interaction.followup.send(
            f"Error fetching Summoner ID for {username}.", ephemeral=True
        )

    guild_id = interaction.guild.id
    channel_id = interaction.channel.id

    if not get_guild(guild_id):
        insert_guild(guild_id, None)

    if get_player(puuid, guild_id):
        return await interaction.followup.send(
            f"Player {username} is already registered here!",
            ephemeral=True
        )

    last_ids = await async_get_last_match(puuid, 1)
    if not last_ids:
        return await interaction.followup.send(
            f"No ranked matches found for {username}.", ephemeral=True
        )
    last_match_id = last_ids[0]

    data = await asyncio.to_thread(get_summoner_rank_details_by_puuid, puuid)
    if not data:
        return await interaction.followup.send(
            f"Unable to retrieve rank for {username}.", ephemeral=True
        )
    tier_str = data["tier"]
    rank_str = data["rank"]
    lp = int(data["lp"])

    insert_player(
        summoner_id,
        puuid,
        username,
        tier_str,
        rank_str,
        lp
    )

    insert_player_guild(
        puuid,
        guild_id,
        channel_id,
        last_match_id
    )

    total = count_players()
    logging.info(
        f"[REGISTER] {username} --> Discord ID : {channel_id} --> Registered : {total}"
    )


    await interaction.followup.send(
        f"> Player **{username}** registered in this server! ✅\n"
        f"> Rank: **{rank_str} {tier_str}** — {lp} LP\n"
        f"> Alerts will be sent in <#{channel_id}>",
        ephemeral=True
    )
    return None


@tree.command(
    name="unregister",
    description="Unregister a player from this server (alerts + leaderboard)"
)
@app_commands.autocomplete(username=username_autocomplete)
async def unregister(interaction: discord.Interaction, username: str):
    guild_id = interaction.guild.id
    username = username.upper()

    player = get_player_by_username(username, guild_id)
    if not player:
        return await interaction.response.send_message(
            f"❌ {username} is not registered on this server.",
            ephemeral=True
        )
    puuid = player[1]

    delete_player(puuid, guild_id)

    lb_id = get_leaderboard_by_guild(guild_id)
    if lb_id is not None:
        delete_leaderboard_member(lb_id, puuid)

        guild_row = get_guild(guild_id)
        lb_channel_id = guild_row[1]
        await leaderboard.update_leaderboard_message(lb_channel_id, client, guild_id)

    await interaction.response.send_message(
        f"✅ Player **{username}** unregistered " +
        ("and removed from the leaderboard." if lb_id is not None else "."),
        ephemeral=True
    )
    return None


@tree.command(name="rank", description="Display a player's current Solo/Duo rank")
@app_commands.autocomplete(username=username_autocomplete)
async def rank(interaction: discord.Interaction, username: str):
    """Show current rank for a registered player."""
    guild_id = interaction.guild.id
    username = username.upper()
    await interaction.response.defer()

    player = get_player_by_username(username, guild_id)
    if not player:
        await interaction.followup.send("This player is not registered here.", ephemeral=True)
        return

    puuid = player[1]
    data = await asyncio.to_thread(get_summoner_rank_details_by_puuid, puuid)
    if not data:
        await interaction.followup.send("Unable to retrieve rank data.", ephemeral=True)
        return

    wins = data['wins']
    losses = data['losses']
    total = wins + losses
    winrate = (wins / total) * 100 if total > 0 else 0.0

    tier = data['tier']
    division = data['rank']
    lp = data['lp']
    tier_files = {
        "IRON": "iron.png",
        "BRONZE": "bronze.png",
        "SILVER": "silver.png",
        "GOLD": "gold.png",
        "PLATINUM": "platinium.png",
        "EMERALD": "emerald.png",
        "DIAMOND": "diamond.png",
        "MASTER": "master.png",
        "GRANDMASTER": "grandmaster.png",
        "CHALLENGER": "challenger.png",
    }
    emblem_file = tier_files.get(tier.upper())
    emblem_path = Path("assets") / emblem_file if emblem_file else None

    if emblem_path and emblem_path.exists():
        file = discord.File(str(emblem_path), filename=emblem_file)
        thumbnail_url = f"attachment://{emblem_file}"
    else:
        thumbnail_url = (
            "https://raw.githubusercontent.com/RiotAPI/"
            "Riot-Games-API-Developer-Assets/master/emblems/"
            f"{tier.capitalize()}.png"
        )

    embed = discord.Embed(
        title=f"{username} rank:",
        description=f"{tier} {division} — {lp} LP",
        color=discord.Color.blue(),
    )
    embed.add_field(name="Wins", value=str(wins), inline=True)
    embed.add_field(name="Losses", value=str(losses), inline=True)
    embed.add_field(name="Winrate", value=f"{winrate:.1f}%", inline=True)
    embed.set_thumbnail(url=thumbnail_url)

    if emblem_path and emblem_path.exists():
        await interaction.followup.send(embed=embed, file=file)
    else:
        await interaction.followup.send(embed=embed)


@tree.command(name="career", description="Display a player's last 10 ranked Solo/Duo games")
@app_commands.autocomplete(username=username_autocomplete)
async def career(interaction: discord.Interaction, username: str):
    """Show the last 10 ranked Solo/Duo games for a registered player."""
    guild_id = interaction.guild.id
    username = username.upper()
    await interaction.response.defer()
    player = get_player_by_username(username, guild_id)
    if not player:
        await interaction.followup.send("This player is not registered!", ephemeral=True)
        return
    puuid = player[1]
    data = await asyncio.to_thread(get_summoner_rank_details_by_puuid, puuid)
    if not data:
        await interaction.followup.send("Error retrieving player rank information!", ephemeral=True)
        return
    rank_info = f"{data['tier']} {data['rank']} {data['lp']} LP"
    match_ids = await async_get_last_match(puuid, 10)
    if not match_ids or not isinstance(match_ids, list):
        await interaction.followup.send("Error retrieving match data or no matches found!", ephemeral=True)
        return
    match_results = []
    for match_id in match_ids:
        details = await async_get_match_details(match_id, puuid)
        if details:
            result, champion, kills, deaths, assists, game_duration, champion_image, damage = details
            match_results.append({
                "result": result,
                "champion": champion,
                "kda": f"{kills}/{deaths}/{assists}",
                "damage": damage,
                "duration": game_duration,
                "champion_image": champion_image
            })
    if not match_results:
        await interaction.followup.send("No match details found for the player's last 10 games.", ephemeral=True)
        return
    embed = discord.Embed(
        title=f"Last 10 Ranked Matches for {username}",
        description=f"Rank: {rank_info}",
        color=discord.Color.blue()
    )
    for i, match in enumerate(match_results):
        result_icon = ":green_circle:" if match["result"] == ':green_circle:' else ":red_circle:"
        embed.add_field(
            name=f"Result: {result_icon}",
            value=(f"**Champion:** {match['champion']}\n"
                   f"**K/D/A:** {match['kda']}\n"
                   f"**Damage:** {match['damage']}\n"
                   f"**Duration:** {match['duration']}\n"),
        )
        if (i + 1) % 2 == 0:
            embed.add_field(name='\u200b', value='\u200b', inline=True)
    await interaction.followup.send(embed=embed)

###############################################################################
# Tâches de fond
###############################################################################

async def check_ingame():
    global players_in_game, players_in_game_messages, CHAMPION_MAPPING

    if not CHAMPION_MAPPING:
        init_champion_mapping()

    while True:
        try:
            players = await async_get_all_players()
            for summoner_id, puuid, username, guild_id, channel_id, *_ in players:
                channel = client.get_channel(int(channel_id))
                if not channel:
                    continue

                champion_id = await is_in_game(puuid)

                player_key = (puuid, guild_id)

                if champion_id is not None and player_key not in players_in_game:
                    champion_name = CHAMPION_MAPPING.get(champion_id)
                    if champion_name:
                        version = get_ddragon_latest_version()
                        champion_image_url = (
                            f"https://ddragon.leagueoflegends.com/cdn/"
                            f"{version}/img/champion/{champion_name}.png"
                        )
                    else:
                        logging.warning(f"[check_ingame] Unknown champion ID {champion_id} in CHAMPION_MAPPING.")
                        champion_image_url = None

                    embed = discord.Embed(
                        title=f"{username} is playing a game!",
                        color=discord.Color.gold()
                    )
                    embed.add_field(name="K/D/A",   value=":hourglass:", inline=True)
                    embed.add_field(name="Damage", value=":hourglass:", inline=True)
                    embed.add_field(name="LP",     value=":hourglass:", inline=True)

                    if champion_image_url:
                        embed.set_thumbnail(url=champion_image_url)

                    try:
                        msg = await channel.send(embed=embed)
                    except discord.Forbidden:
                        logging.warning(
                            f"[check_ingame] Missing access to channel {channel_id}. Disabling alerts."
                        )
                        update_player_guild(puuid, guild_id, channel_id=0)
                        msg = None

                    except discord.DiscordException as e:
                        logging.error(f"[check_ingame] Failed to send in-game embed: {e}")
                        msg = None
                    if msg:
                        players_in_game.add(player_key)
                        players_in_game_messages[player_key] = msg

                    # Don't remove the player here. The check_for_game_completion task
                    # will take care of cleanup once the match ID changes.
        except Exception as e:
            logging.error(f"[check_ingame] Unexpected error: {e}", exc_info=True)

        await asyncio.sleep(15)


async def check_for_game_completion():
    """
    Pour chaque joueur marqué « in game », vérifie s'il a terminé sa partie.
    Quand la partie se termine :
      1) on met à jour player_guild.last_match_id
      2) on met à jour player global (tier, rank, LP)
      3) on supprime l'embed « En partie »
      4) on envoie l'embed de résumé de fin de partie
      5) on met à jour le message du leaderboard dans le salon configuré
      6) on retire le joueur de players_in_game
    """

    global players_in_game, players_in_game_messages, recent_match_lp_changes

    while True:
        try:
            now = time.time()
            recent_match_lp_changes = {
                k: v for k, v in recent_match_lp_changes.items()
                if now - v[1] < MATCH_CACHE_EXPIRATION
            }

            players = await async_get_all_players()
            player_map = {(row[1], row[3]): row for row in players}

            for player_key in list(players_in_game):
                row = player_map.get(player_key)
                if not row:
                    players_in_game.discard(player_key)
                    players_in_game_messages.pop(player_key, None)
                    continue

                (
                    summoner_id,
                    puuid,
                    username,
                    guild_id,
                    alert_channel_id,
                    last_match_id,
                    old_tier,
                    old_rank,
                    old_lp,
                    *_
                ) = row

                if await async_is_in_game(puuid):
                    continue

                last_matches = await async_get_last_match(puuid, 1)
                if not last_matches:
                    continue
                new_match_id = last_matches[0]
                if new_match_id == last_match_id:
                    continue

                details = await async_get_match_details(new_match_id, puuid)
                if not details:
                    continue
                result, champion, kills, deaths, assists, game_duration, champ_img, damage = details

                key = (puuid, new_match_id)
                if key in recent_match_lp_changes:
                    lp_change = recent_match_lp_changes[key][0]
                    tier_str = old_tier
                    rank_str = old_rank
                    new_lp = old_lp + lp_change
                else:
                    new_details = await asyncio.to_thread(
                        get_summoner_rank_details_by_puuid, puuid
                    )
                    if not new_details:
                        tier_str = old_tier
                        rank_str = old_rank
                        new_lp = old_lp
                    else:
                        try:
                            tier_str = new_details["tier"]
                            rank_str = new_details["rank"]
                            new_lp = int(new_details["lp"])
                        except Exception as e:
                            logging.error(
                                f"Error parsing new rank info: {e}"
                            )
                            tier_str = old_tier
                            rank_str = old_rank
                            new_lp = old_lp

                    lp_change = calculate_lp_change(
                        old_tier, old_rank, old_lp,
                        new_tier=tier_str, new_rank=rank_str, new_lp=new_lp
                    )
                    recent_match_lp_changes[key] = (lp_change, now)

                    update_player_global(
                        puuid,
                        tier=tier_str,
                        rank=rank_str,
                        lp=new_lp,
                        lp_change=lp_change
                    )

                update_player_guild(
                    puuid,
                    guild_id,
                    last_match_id=new_match_id
                )

                player_key = (puuid, guild_id)
                in_game_msg = players_in_game_messages.pop(player_key, None)
                if in_game_msg:
                    try:
                        await in_game_msg.delete()
                    except discord.DiscordException as e:
                        logging.error(f"[check_for_game_completion] Failed to delete in-game message: {e}")

                alert_channel = client.get_channel(int(alert_channel_id))
                if alert_channel:
                    await send_match_result_embed(
                        alert_channel,
                        username,
                        result,
                        kills,
                        deaths,
                        assists,
                        champ_img,
                        lp_change,
                        damage
                    )

                guild_data = get_guild(guild_id)  # (guild_id, leaderboard_channel_id)
                lb_channel_id = guild_data[1] if guild_data else None
                if lb_channel_id:
                    await leaderboard.update_leaderboard_message(lb_channel_id, client, guild_id)

                players_in_game.discard(player_key)
                logging.info(
                    f"[MATCH FINISHED] {username}: "
                    f"Old LP: {old_lp} New LP: {new_lp} Difference: {lp_change}"
                )

        except Exception as e:
            logging.error(f"[check_for_game_completion] Unexpected error: {e}", exc_info=True)

        await asyncio.sleep(10)


async def send_match_result_embed(channel, username, result, kills, deaths, assists,
                                  champion_image, lp_change, damage):
    game_result = "Victory" if result == ':green_circle:' else "Defeat"
    lp_text = "LP Win" if lp_change > 0 else "LP Lost"
    embed = discord.Embed(
        title=f"{game_result} for {username}",
        color=discord.Color.green() if result == ':green_circle:' else discord.Color.red()
    )
    embed.add_field(name="K/D/A", value=f"{kills}/{deaths}/{assists}", inline=True)
    embed.add_field(name="Damage", value=f"{damage}", inline=True)
    embed.add_field(name=lp_text, value=f"{'+' if lp_change > 0 else ''}{lp_change} LP", inline=True)
    embed.set_thumbnail(url=champion_image)
    try:
        await channel.send(embed=embed)
    except discord.DiscordException as e:
        logging.error(f"[send_match_result_embed] Failed to send match result: {e}")


async def handle_music_reaction(payload: discord.RawReactionActionEvent):
    """Play a sound when a user reacts to a victory or defeat embed."""
    emoji = str(payload.emoji)
    if emoji not in MUSIC_REACTIONS:
        return

    guild = client.get_guild(payload.guild_id)
    if not guild:
        return

    channel = guild.get_channel(payload.channel_id)
    if not channel:
        return
    try:
        message = await channel.fetch_message(payload.message_id)
    except discord.DiscordException:
        return

    if message.author != client.user or not message.embeds:
        return

    title = message.embeds[0].title or ""
    if not any(keyword in title for keyword in ("Victory", "Defeat", "is playing a game")):
        return

    try:
        member = await guild.fetch_member(payload.user_id)
        if member.bot or not member.voice or not member.voice.channel:
            return
    except (discord.NotFound, discord.DiscordException):
        return

    audio_path = MUSIC_REACTIONS[emoji]
    if not audio_path.exists():
        return

    voice_client = guild.voice_client
    voice_channel = member.voice.channel
    if not voice_client:
        try:
            voice_client = await voice_channel.connect()
        except discord.DiscordException:
            return

    try:
        voice_client.play(discord.FFmpegPCMAudio(str(audio_path)))
        while voice_client.is_playing():
            await asyncio.sleep(1)
    except discord.DiscordException:
        pass
    finally:
        try:
            await voice_client.disconnect()
        except discord.DiscordException:
            pass


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    await handle_music_reaction(payload)

@client.event
async def on_ready():
    await tree.sync()
    create_db()
    logging.info(f"Bot connected as {client.user}")
    init_champion_mapping()
    asyncio.create_task(check_ingame())
    asyncio.create_task(check_for_game_completion())
    asyncio.create_task(check_username_changes())
    asyncio.create_task(reset_lp_scheduler(client))


client.run(DISCORD_TOKEN)