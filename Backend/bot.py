import asyncio
import logging
import os
import time
import tracemalloc
from datetime import timedelta
from pathlib import Path
import aiohttp
import discord
import requests
from discord import app_commands
from dotenv import load_dotenv

import leaderboard
from create_db import create_db
from fonction_bdd import (
    insert_player,
    get_player_by_username,
    delete_player,
    username_autocomplete,
    get_player,
    get_all_players,
    get_guild,
    insert_guild,
    insert_player_guild,
    update_player_guild,
    update_player_global,
    get_leaderboard_by_guild,
    delete_leaderboard_member,
    count_players,
    set_guild_flex_mode,
    set_recap_mode,
)
from leaderboard_tasks import reset_lp_scheduler
from log import DiscordLogHandler

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

DISCORD_LOG_CHANNEL_ID = 1392503284190679203
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

# Mapping of simple region codes to platform and cluster
REGION_MAP = {
    "euw": ("euw1", "europe"),
    "eune": ("eun1", "europe"),
    "na": ("na1", "americas"),
    "kr": ("kr", "asia"),
    "br": ("br1", "americas"),
    "jp": ("jp1", "asia"),
    "lan": ("la1", "americas"),
    "las": ("la2", "americas"),
    "oce": ("oc1", "americas"),
    "ru": ("ru", "europe"),
    "tr": ("tr1", "europe"),
    "vn": ("vn2", "sea"),
}

PLATFORM_TO_CLUSTER = {platform: cluster for platform, cluster in REGION_MAP.values()}

REGION_CHOICES = [
    app_commands.Choice(name=key.upper(), value=key)
    for key in REGION_MAP.keys()
]

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
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt == retries:
                logging.error(f"Error fetching {url}: {e}")
                return None
            await asyncio.sleep(backoff * attempt)

##############################################################################
# Fonctions d'accès à l'API Riot (appel synchrones via requests)
##############################################################################

def get_puuid(username, hashtag, cluster: str):
    url = f"https://{cluster}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{username}/{hashtag}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    data = fetch_json(url, headers=headers)
    return data.get('puuid') if data else None

def get_summoner_rank_details_by_puuid(puuid: str, queue: str = "RANKED_SOLO_5x5", platform: str = "euw1"):
    """Return detailed rank info for a specific queue using the PUUID directly."""
    url = (
        f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-puuid/"
        f"{puuid}"
    )
    headers = {"X-Riot-Token": RIOT_API_KEY}
    data = fetch_json(url, headers=headers)
    if isinstance(data, list):
        for entry in data:
            if entry.get("queueType") == queue:
                return {
                    "tier": entry.get("tier"),
                    "rank": entry.get("rank"),
                    "lp": entry.get("leaguePoints"),
                    "wins": entry.get("wins"),
                    "losses": entry.get("losses"),
                }
    return None

def get_last_match(puuid, nb_last_match, cluster: str):
    url = f"https://{cluster}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?type=ranked&count={nb_last_match}"
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


def get_match_details(match_id: str, puuid: str, cluster: str):
    """
    Récupère les détails d'un match classé (.match/v5) pour un joueur donné (par son PUUID).
    Construit aussi l’URL de l’image du champion en utilisant la version Data Dragon la plus récente.
    """
    if not match_id:
        logging.error("No match ID provided.")
        return None

    url = f"https://{cluster}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    match_data = fetch_json(url, headers=headers)
    if not match_data:
        return None
    queue_id = match_data.get("info", {}).get("queueId")
    if queue_id not in (420, 440):
        return None

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
            puuid, old_username, _, _, region, *_ = player

            cluster = PLATFORM_TO_CLUSTER.get(region, "europe")
            url = f"https://{cluster}.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
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
        if old_lp is None or new_lp is None or not old_rank or not new_rank:
            return 0
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


async def is_in_game(puuid: str, region: str, flex: bool = False) -> int | None:
    """Retourne le championId si le joueur est actuellement en ranked.

    L'API spectator peut fournir des parties Flex (queue 440) ou Solo/Duo
    (queue 420). Certains comptes sont identifiés par ``puuid`` ou par
    ``summonerId`` selon l'endpoint. Pour couvrir tous les cas, on vérifie
    la présence des deux champs et on accepte les deux codes de file.

    Le paramètre ``flex`` est conservé pour compatibilité mais n'influence
    plus la détection.
    """

    url = (
        f"https://{region}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/"
        f"{puuid}"
    )
    headers = {"X-Riot-Token": RIOT_API_KEY}

    data = await async_fetch_json(url, headers=headers)
    if not data:
        return None

    queue_id = data.get("gameQueueConfigId")
    if queue_id not in (420, 440):
        return None

    for participant in data.get("participants", []):
        pid = participant.get("puuid") or participant.get("summonerId")
        if pid == puuid:
            return participant.get("championId")
    return None


###############################################################################
# Wrappers asynchrones pour les appels bloquants
###############################################################################
async def async_get_all_players():
    return await asyncio.to_thread(get_all_players)

async def async_is_in_game(puuid, region, flex: bool = False):
    return await is_in_game(puuid, region, flex)

async def async_get_last_match(puuid, nb_last_match, cluster):
    return await asyncio.to_thread(get_last_match, puuid, nb_last_match, cluster)

async def async_get_match_details(match_id, puuid, cluster):
    return await asyncio.to_thread(get_match_details, match_id, puuid, cluster)


###############################################################################
# Commandes (register, unregister, rank, career)
###############################################################################

@tree.command(
    name="register",
    description="Register a player in this server and activate alert"
)
@app_commands.describe(
    gamename="The player's Riot in game name",
    tagline="The player's #",
    region="Player region"
)
@app_commands.choices(region=REGION_CHOICES)
async def register(
        interaction: discord.Interaction,
        gamename: str,
        tagline: str,
        region: app_commands.Choice[str],
):
    await interaction.response.defer(ephemeral=True)
    username = f"{gamename.upper()}#{tagline.upper()}"
    region_key = region.value.lower()
    mapping = REGION_MAP.get(region_key)
    if not mapping:
        return await interaction.followup.send(
            "Invalid region. Choose from: euw, eune, na, kr, br, jp, lan, las, oce, ru, tr, vn.",
            ephemeral=True,
        )
    platform, cluster = mapping
    try:
        riot_username, hashtag = username.split("#")
    except ValueError:
        return await interaction.followup.send(
            "Invalid username format. Use USERNAME#HASHTAG.",
            ephemeral=True
        )

    puuid = await asyncio.to_thread(get_puuid, riot_username, hashtag, cluster)
    if not puuid:
        return await interaction.followup.send(
            f"Error fetching PUUID for {username}.", ephemeral=True
        )

    guild_id = interaction.guild.id
    channel_id = interaction.channel.id

    if not get_guild(guild_id):
        insert_guild(guild_id, None, 0)

    if get_player(puuid, guild_id):
        return await interaction.followup.send(
            f"Player {username} is already registered here!",
            ephemeral=True
        )

    last_ids = await async_get_last_match(puuid, 1, cluster)
    if not last_ids:
        return await interaction.followup.send(
            f"No ranked matches found for {username}.", ephemeral=True
        )
    last_match_id = last_ids[0]

    solo_data = await asyncio.to_thread(get_summoner_rank_details_by_puuid, puuid, "RANKED_SOLO_5x5", platform)
    flex_data = await asyncio.to_thread(get_summoner_rank_details_by_puuid, puuid, "RANKED_FLEX_SR", platform)
    if not solo_data:
        return await interaction.followup.send(
            f"Unable to retrieve rank for {username}.", ephemeral=True
        )

    rank_str = solo_data["tier"]
    tier_str = solo_data["rank"]
    lp = int(solo_data["lp"])

    flex_rank_str = flex_data["tier"] if flex_data else None
    flex_tier_str = flex_data["rank"] if flex_data else None
    flex_lp = int(flex_data["lp"]) if flex_data else None

    insert_player(
        puuid,
        username,
        tier_str,
        rank_str,
        lp,
        platform,
        flex_tier_str,
        flex_rank_str,
        flex_lp,
    )

    insert_player_guild(
        puuid,
        guild_id,
        channel_id,
        last_match_id
    )

    total = count_players()
    user = interaction.user
    logging.info(
        f"[REGISTER] {username} --> User: {user} ({user.id}) --> Channel ID: {channel_id} --> Registered: {total}"
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
    puuid = player[0]

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


@tree.command(name="flex", description="Enable or disable Flex queue alerts")
@app_commands.describe(mode="Choose 'enable' to track Flex queue games or 'disable' to monitor Solo queue")
@app_commands.choices(mode=[
    app_commands.Choice(name="enable", value="enable"),
    app_commands.Choice(name="disable", value="disable"),
])
async def flex(interaction: discord.Interaction, mode: str):
    guild_id = interaction.guild.id
    row = get_guild(guild_id)

    enable = mode.lower() == "enable"

    if row is None:
        insert_guild(guild_id, None, 1 if enable else 0)
    else:
        set_guild_flex_mode(guild_id, enable)

    await interaction.response.send_message(
        f"Flex mode {'enabled' if enable else 'disabled'}.",
        ephemeral=True
    )
    return None

@tree.command(name="recap", description="Enable or disable daily/weekly recaps")
@app_commands.choices(period=[
    app_commands.Choice(name="daily", value="daily"),
    app_commands.Choice(name="weekly", value="weekly"),
])
@app_commands.choices(mode=[
    app_commands.Choice(name="enable", value="enable"),
    app_commands.Choice(name="disable", value="disable"),
])
@app_commands.describe(period="Choose daily or weekly recap", mode="Enable or disable the recap")
async def recap(interaction: discord.Interaction, period: str, mode: str):
    enable = mode.lower() == "enable"
    set_recap_mode(interaction.guild.id, period, enable)
    await interaction.response.send_message(
        f"{period.capitalize()} recap {'enabled' if enable else 'disabled'}.",
        ephemeral=True,
    )
    return None


@tree.command(name="help", description="Get a link to the help server")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Need help? Join our support server: https://discord.gg/vZHPkBHmkC",
        ephemeral=True,
    )
    return None


@tree.command(name="howtosetup", description="Learn how to configure the bot")
async def howtosetup_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        (
            "To set up the bot: \n"
            "- /register --> adds players\n"
            "- /leaderboard --> creates a leaderboard channel\n"
            "- /recap daily|weekly enable --> enables recap messages\n"
            "For more help join : https://discord.gg/vZHPkBHmkC"
        ),
        ephemeral=True,
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

    puuid = player[0]
    region = player[4]
    data = await asyncio.to_thread(get_summoner_rank_details_by_puuid, puuid, "RANKED_SOLO_5x5", region)
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
    emblem_path = Path("/assets") / emblem_file if emblem_file else None

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
    puuid = player[0]
    region = player[4]
    cluster = PLATFORM_TO_CLUSTER.get(region, "europe")
    data = await asyncio.to_thread(get_summoner_rank_details_by_puuid, puuid, "RANKED_SOLO_5x5", region)
    if not data:
        await interaction.followup.send("Error retrieving player rank information!", ephemeral=True)
        return
    rank_info = f"{data['tier']} {data['rank']} {data['lp']} LP"
    match_ids = await async_get_last_match(puuid, 10, cluster)
    if not match_ids or not isinstance(match_ids, list):
        await interaction.followup.send("Error retrieving match data or no matches found!", ephemeral=True)
        return
    match_results = []
    for match_id in match_ids:
        details = await async_get_match_details(match_id, puuid, cluster)
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
            guild_flex: dict[int, bool] = {}
            for puuid, username, guild_id, channel_id, region, *_ in players:
                channel = client.get_channel(int(channel_id))
                if not channel:
                    continue

                flex_mode = guild_flex.get(guild_id)
                if flex_mode is None:
                    guild_row = get_guild(guild_id)
                    flex_mode = bool(guild_row[2]) if guild_row else False
                    guild_flex[guild_id] = flex_mode

                champion_id = await is_in_game(puuid, region, flex_mode)

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
                            f"[check_ingame] Missing access to channel {channel_id}."
                        )
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
            player_map = {(row[0], row[2]): row for row in players}

            for player_key in list(players_in_game):
                row = player_map.get(player_key)
                if not row:
                    players_in_game.discard(player_key)
                    players_in_game_messages.pop(player_key, None)
                    continue

                (
                    puuid,
                    username,
                    guild_id,
                    alert_channel_id,
                    region,
                    last_match_id,
                    solo_tier,
                    solo_rank,
                    solo_lp,
                    _lp24h,
                    _lp7d,
                    flex_tier,
                    flex_rank,
                    flex_lp,
                ) = row

                guild_row = get_guild(guild_id)
                flex_mode = bool(guild_row[2]) if guild_row else False
                if await async_is_in_game(puuid, region, flex_mode):
                    continue

                cluster = PLATFORM_TO_CLUSTER.get(region, "europe")

                last_matches = await async_get_last_match(puuid, 1, cluster)
                if not last_matches:
                    continue
                new_match_id = last_matches[0]
                if new_match_id == last_match_id:
                    continue

                details = await async_get_match_details(new_match_id, puuid, cluster)
                if not details:
                    continue
                result, champion, kills, deaths, assists, game_duration, champ_img, damage = details

                match = await async_fetch_json(
                    f"https://{cluster}.api.riotgames.com/lol/match/v5/matches/{new_match_id}",
                    headers={"X-Riot-Token": RIOT_API_KEY}
                )
                queue_id = match.get("info", {}).get("queueId") if match else None
                if queue_id not in (420, 440):
                    continue
                is_flex_match = queue_id == 440
                is_early_surrender = False
                if match and match.get("info"):
                    participants = match["info"].get("participants", [])
                    is_early_surrender = any(p.get("gameEndedInEarlySurrender") for p in participants)

                if is_flex_match:
                    old_tier, old_rank, old_lp = flex_tier, flex_rank, flex_lp
                else:
                    old_tier, old_rank, old_lp = solo_tier, solo_rank, solo_lp

                key = (puuid, new_match_id)
                if key in recent_match_lp_changes:
                    lp_change = recent_match_lp_changes[key][0]
                    tier_str = old_tier
                    rank_str = old_rank
                    new_lp = old_lp + lp_change
                else:
                    queue_str = "RANKED_FLEX_SR" if is_flex_match else "RANKED_SOLO_5x5"
                    new_details = await asyncio.to_thread(
                        get_summoner_rank_details_by_puuid, puuid, queue_str, region
                    )
                    if not new_details:
                        tier_str = old_tier
                        rank_str = old_rank
                        new_lp = old_lp
                    else:
                        try:

                            # API returns tier (e.g. GOLD) and rank (e.g. II)
                            # Convert so tier_str stores the division and
                            # rank_str stores the rank category.
                            rank_str = new_details["tier"]
                            tier_str = new_details["rank"]

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

                    if is_flex_match:
                        update_player_global(
                            puuid,
                            flex_tier=tier_str,
                            flex_rank=rank_str,
                            flex_lp=new_lp,
                            lp_change=lp_change
                        )
                    else:
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
                        damage,
                        is_early_surrender
                    )

                guild_data = guild_row  # (guild_id, leaderboard_channel_id, flex_enabled)
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
                                  champion_image, lp_change, damage, is_early_surrender: bool = False):
    if is_early_surrender:
        game_result = "Early Surrender"
        color = discord.Color.orange()
    else:
        game_result = "Victory" if result == ':green_circle:' else "Defeat"
        color = discord.Color.green() if result == ':green_circle:' else discord.Color.red()
    lp_text = "LP Win" if lp_change > 0 else "LP Lost"
    embed = discord.Embed(
        title=f"{game_result} for {username}",
        color=color
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

    member = guild.get_member(payload.user_id)
    if member is None or member.bot or not member.voice or not member.voice.channel:
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


async def handle_spectate_reaction(payload: discord.RawReactionActionEvent):
    """Send a spectate command when reacting with the projector emoji."""
    if str(payload.emoji) != "📽️":
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
    if "is playing a game" not in title:
        return

    puuid = None
    for (p, g), msg in players_in_game_messages.items():
        if msg.id == message.id:
            puuid = p
            break
    if not puuid:
        return

    player = get_player(puuid, payload.guild_id)
    if not player:
        return

    region = player[4]

    data = await async_fetch_json(
        f"https://{region}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}",
        headers={"X-Riot-Token": RIOT_API_KEY},
    )
    if not data:
        return

    await channel.send("Spectate information available.")


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    await handle_music_reaction(payload)
    await handle_spectate_reaction(payload)

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
