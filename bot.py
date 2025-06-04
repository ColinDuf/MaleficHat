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
from fonction_bdd import (insert_player, get_player_by_username, delete_player, username_autocomplete, get_player, \
                          get_all_players, get_guild, insert_guild, insert_player_guild, update_player_guild,
                          update_player_global, get_leaderboard_by_guild, delete_leaderboard_member,
                          )
import requests
import tracemalloc
from log import DiscordLogHandler

tracemalloc.start()
load_dotenv()
logging.basicConfig(level=logging.INFO)

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
RIOT_API_KEY = os.getenv('RIOT_API_KEY')

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
leaderboard.setup_tree(tree)

DISCORD_LOG_CHANNEL_ID = 1379139184635154442
discord_handler = DiscordLogHandler(client, DISCORD_LOG_CHANNEL_ID)
discord_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
discord_handler.setFormatter(formatter)
logging.getLogger().addHandler(discord_handler)

players_in_game: set[str] = set()
players_in_game_messages: dict[str, discord.Message] = {}
CHAMPION_MAPPING: dict[int, str] = {}

##############################################################################
# Fonctions d'accès à l'API Riot (appel synchrones via requests)
##############################################################################

def get_puuid(username, hashtag):
    url = f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{username}/{hashtag}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get('puuid')
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching PUUID: {e}")
        return None

def get_summoner_id(puuid):
    url = f"https://euw1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get('id')
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching summoner ID: {e}")
        return None

def get_summoner_rank(summoner_id):
    url = f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        ranks = response.json()
        for rank in ranks:
            if rank['queueType'] == 'RANKED_SOLO_5x5':
                # Exemple de résultat : "GOLD I 50 LP"
                return f"{rank['tier']} {rank['rank']} {rank['leaguePoints']} LP"
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching summoner rank: {e}")
    return "Unknown"

def get_last_match(puuid, nb_last_match):
    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?type=ranked&count={nb_last_match}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        matches = response.json()
        if isinstance(matches, list) and matches:
            return matches
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching last matches: {e}")
        return None


def get_ddragon_latest_version() -> str:
    """
    Récupère la liste des versions Data Dragon depuis Riot,
    et retourne la première (la plus récente)".
    """
    try:
        versions_url = "https://ddragon.leagueoflegends.com/api/versions.json"
        response = requests.get(versions_url)
        response.raise_for_status()
        versions = response.json()
        if isinstance(versions, list) and len(versions) > 0:
            return versions[0]
        else:
            logging.error("Impossible de récupérer la version Data Dragon : réponse inattendue.")
    except requests.RequestException as e:
        logging.error(f"Erreur lors de la récupération des versions Data Dragon : {e}")
    return "25.11"


def init_champion_mapping() -> None:
    """
    Utilise get_ddragon_latest_version() pour récupérer la dernière version,
    puis charge le champ 'champion.json' correspondant, afin de remplir
    CHAMPION_MAPPING = { int(key) : name } pour chaque champion.
    """
    global CHAMPION_MAPPING

    version = get_ddragon_latest_version()

    try:
        url_champs = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
        resp = requests.get(url_champs)
        resp.raise_for_status()
        data = resp.json().get("data", {})
    except requests.RequestException as e:
        logging.error(f"[DataDragon] Impossible de récupérer champion.json pour la version {version} : {e}")
        data = {}

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
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        match_data = response.json()

        game_mode = match_data.get("info", {}).get("queueId")
        if game_mode == 420:
            # Récupère la version Data Dragon à la volée
            ddragon_version = get_ddragon_latest_version()

            for participant in match_data["info"]["participants"]:
                if participant["puuid"] == puuid:
                    # Résultat (victoire/défaite)
                    result = ":green_circle:" if participant.get("win") else ":red_circle:"
                    champion = participant.get("championName", "")
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

                    champion_image = (
                        f"https://ddragon.leagueoflegends.com/cdn/"
                        f"{ddragon_version}/img/champion/{champion}.png"
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

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching match details: {e}")

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

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            current_username = (
                                    data.get("gameName", "").upper() +
                                    "#" +
                                    data.get("tagLine", "").upper()
                            )
                            if current_username != old_username:
                                update_player_global(puuid, username=current_username)
                                logging.info(
                                    f"Username mis à jour : {old_username} → {current_username}"
                                )
                        else:
                            logging.warning(
                                f"❌ Erreur récupération Riot pour PUUID {puuid} (status {response.status})"
                            )
            except Exception as e:
                logging.error(f"Erreur de requête API pour {puuid}: {e}")

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
            # Même division → on renvoie juste la différence de LP
            if old_tier == new_tier:
                return new_lp - old_lp

            # Même catégorie, division différente
            tier_diff = (tier_order.index(new_tier) - tier_order.index(old_tier)) * 100
            return tier_diff + (new_lp - old_lp)

        # Changement de catégorie (rank)
        rank_diff = (rank_order.index(new_rank) - rank_order.index(old_rank)) * 400
        tier_diff = (tier_order.index(new_tier) - tier_order.index(old_tier)) * 100
        return rank_diff + tier_diff + (new_lp - old_lp)

    except ValueError as e:
        logging.error(f"[ERREUR LP] Mauvaise valeur de tier/rank : {e}")
        return 0


async def is_in_game(puuid: str) -> int | None:
    """
    Si le joueur est en ranked solo/duo (queue 420), renvoie son championId (int).
    Sinon renvoie None.
    """
    url = f"https://euw1.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
    headers = {"X-Riot-Token": RIOT_API_KEY}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("gameQueueConfigId") != 420:
                        return None
                    for participant in data.get("participants", []):
                        if participant.get("puuid") == puuid:
                            return participant.get("championId")
                    return None
                elif response.status == 404:
                    return None
                else:
                    logging.warning(f"[Spectator] statut inattendu {response.status} pour puuid={puuid}")
                    return None
    except aiohttp.ClientError as e:
        logging.error(f"Erreur HTTP Spectator V5 : {e}")
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

    rank_info = await asyncio.to_thread(get_summoner_rank, summoner_id)
    if rank_info == "Unknown":
        return await interaction.followup.send(
            f"Unable to retrieve rank for {username}.", ephemeral=True
        )
    try:
        rank_str, tier_str, lp_str, _ = rank_info.split()
        lp = int(lp_str)
    except Exception as e:
        logging.error(f"Error parsing rank info: {e}")
        return await interaction.followup.send(
            "Error parsing rank information.", ephemeral=True
        )

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

    logging.info(f"[REGISTER] {username} --> Discord ID : {channel_id}")


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
            f"❌ {username} n'est pas enregistré sur ce serveur.",
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
        f"✅ Joueur **{username}** désinscrit " +
        ("et retiré du leaderboard." if lb_id is not None else "."),
        ephemeral=True
    )
    return None


@tree.command(name="career", description="Display a player's last 10 ranked Solo/Duo games")
@app_commands.autocomplete(username=username_autocomplete)
async def career(interaction: discord.Interaction, username: str):
    username = username.upper()
    await interaction.response.defer()
    player = get_player_by_username(username)
    if not player:
        await interaction.followup.send("This player is not registered!", ephemeral=True)
        return
    puuid = player[1]
    summoner_id = player[0]
    rank_info = await asyncio.to_thread(get_summoner_rank, summoner_id)
    if rank_info == "Unknown":
        await interaction.followup.send("Error retrieving player rank information!", ephemeral=True)
        return
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
        players = await async_get_all_players()
        for summoner_id, puuid, username, guild_id, channel_id, *_ in players:
            channel = client.get_channel(int(channel_id))
            if not channel:
                continue

            champion_id = await is_in_game(puuid)

            if champion_id is not None and puuid not in players_in_game:
                champion_name = CHAMPION_MAPPING.get(champion_id)
                if champion_name:
                    version = get_ddragon_latest_version()
                    champion_image_url = (
                        f"https://ddragon.leagueoflegends.com/cdn/"
                        f"{version}/img/champion/{champion_name}.png"
                    )
                else:
                    logging.warning(f"[check_ingame] Champion ID {champion_id} inconnu dans CHAMPION_MAPPING.")
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

                msg = await channel.send(embed=embed)
                players_in_game.add(puuid)
                players_in_game_messages[puuid] = msg

            elif champion_id is None and puuid in players_in_game:
                players_in_game.discard(puuid)

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

    global players_in_game, players_in_game_messages

    while True:
        players = await async_get_all_players()
        player_map = {row[1]: row for row in players}

        for puuid in list(players_in_game):
            row = player_map.get(puuid)
            if not row:
                players_in_game.discard(puuid)
                players_in_game_messages.pop(puuid, None)
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

            new_rank_info = await asyncio.to_thread(get_summoner_rank, summoner_id)
            if new_rank_info == "Unknown":
                tier_str = old_tier
                rank_str = old_rank
                new_lp = old_lp
            else:
                try:
                    rank_str, tier_str, lp_str, _ = new_rank_info.split()
                    new_lp = int(lp_str)
                except Exception as e:
                    logging.error(f"Error parsing new rank info: {e}")
                    tier_str = old_tier
                    rank_str = old_rank
                    new_lp = old_lp

            lp_change = calculate_lp_change(
                old_tier, old_rank, old_lp,
                new_tier=tier_str, new_rank=rank_str, new_lp=new_lp
            )

            update_player_guild(
                puuid,
                guild_id,
                last_match_id=new_match_id
            )
            update_player_global(
                puuid,
                tier=tier_str,
                rank=rank_str,
                lp=new_lp,
                lp_change=lp_change
            )

            in_game_msg = players_in_game_messages.pop(puuid, None)
            if in_game_msg:
                try:
                    await in_game_msg.delete()
                except Exception:
                    pass

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
            else:
                logging.warning(f"[Leaderboard] Pas de salon configuré pour guilde {guild_id}")

            players_in_game.discard(puuid)
            # Log the result of the match in English with more details
            lp_diff = new_lp - old_lp
            sign = '+' if lp_diff >= 0 else ''
            logging.info(
                f"[MATCH FINISHED] {username}: last LP = {old_lp}, "
                f"new LP = {new_lp}, change = {sign}{lp_diff}"
            )

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
    await channel.send(embed=embed)

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
