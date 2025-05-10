import discord
from discord import app_commands
import os
import logging
import asyncio
from datetime import timedelta
from dotenv import load_dotenv
from create_db import create_db
from leaderboard_tasks import leaderboard_update_event
import leaderboard
from fonction_bdd import (
    insert_player, get_player_by_username, update_player, delete_player,
    username_autocomplete, get_player, get_all_players
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

# (Optionnel) Configuration du logging vers un salon Discord (décommentez si besoin)
# DISCORD_LOG_CHANNEL_ID = 1352790668174557267
# discord_handler = DiscordLogHandler(client, DISCORD_LOG_CHANNEL_ID)
# discord_handler.setLevel(logging.INFO)
# formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# discord_handler.setFormatter(formatter)
# logging.getLogger().addHandler(discord_handler)

# Ensemble global pour suivre les joueurs déjà notifiés comme en game
players_in_game = set()

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
    url = f"https://europe.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
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

def get_match_details(match_id, puuid):
    if not match_id:
        logging.error("No match ID provided.")
        return None
    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        match_data = response.json()
        game_mode = match_data['info']['queueId']
        if game_mode == 420:
            for participant in match_data['info']['participants']:
                if participant['puuid'] == puuid:
                    result = ':green_circle:' if participant['win'] else ':red_circle:'
                    champion = participant['championName']
                    kills = participant['kills']
                    deaths = participant['deaths']
                    assists = participant['assists']
                    damage = participant['totalDamageDealtToChampions']
                    game_duration_seconds = match_data['info']['gameDuration']
                    game_duration = (str(timedelta(seconds=game_duration_seconds))
                                     if game_duration_seconds >= 3600
                                     else f"{game_duration_seconds // 60}:{game_duration_seconds % 60:02d}")
                    # Pour obtenir l'image du champion via Data Dragon
                    champion_image = f"https://ddragon.leagueoflegends.com/cdn/13.1.1/img/champion/{champion}.png"
                    return result, champion, kills, deaths, assists, game_duration, champion_image, damage
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching match details: {e}")
    return None

def calculate_lp_change(old_tier, old_rank, old_lp, new_tier, new_rank, new_lp):
    tier_order = ['IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']
    rank_order = ['I', 'II', 'III', 'IV']
    if old_tier == new_tier:
        if old_rank == new_rank:
            return new_lp - old_lp
        else:
            return (rank_order.index(new_rank) - rank_order.index(old_rank)) * 100 + (new_lp - old_lp)
    else:
        tier_diff = (tier_order.index(new_tier) - tier_order.index(old_tier)) * 400
        rank_diff = (rank_order.index(new_rank) - rank_order.index(old_rank)) * 100
        return tier_diff + rank_diff + (new_lp - old_lp)

# Modification de is_in_game pour utiliser le puuid
def is_in_game(puuid):
    """
    Vérifie si un joueur est en game en utilisant le puuid.
    (Remarque : Vérifiez bien que cet endpoint accepte le puuid.)
    """
    url = f"https://euw1.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking in-game status: {e}")
        return False

###############################################################################
# Wrappers asynchrones pour les appels bloquants
###############################################################################
async def async_get_all_players():
    from fonction_bdd import get_all_players
    return await asyncio.to_thread(get_all_players)

async def async_is_in_game(puuid):
    return await asyncio.to_thread(is_in_game, puuid)

async def async_get_last_match(puuid, nb_last_match):
    return await asyncio.to_thread(get_last_match, puuid, nb_last_match)

async def async_get_match_details(match_id, puuid):
    return await asyncio.to_thread(get_match_details, match_id, puuid)

###############################################################################
# Commandes (register, unregister, rank, career)
###############################################################################
@tree.command(name="register", description="Register a player in this server and activate alert")
@app_commands.describe(gamename="The player's Riot in game name", tagline="The player's #")
async def register(interaction: discord.Interaction, gamename: str, tagline: str):
    await interaction.response.defer(ephemeral=True)
    username = gamename.upper() + "#" + tagline.upper()
    guild_id = str(interaction.guild.id)
    try:
        riot_username, hashtag = username.split('#')
    except ValueError:
        await interaction.followup.send("Invalid username format. Use USERNAME#HASHTAG.", ephemeral=True)
        return
    puuid = await asyncio.to_thread(get_puuid, riot_username, hashtag)
    if not puuid:
        await interaction.followup.send(f"Error fetching PUUID for {username}.", ephemeral=True)
        return
    summoner_id = await asyncio.to_thread(get_summoner_id, puuid)
    if not summoner_id:
        await interaction.followup.send(f"Error fetching Summoner ID for {username}.", ephemeral=True)
        return
    if get_player(puuid, guild_id):
        await interaction.followup.send(f"Player {username} is already registered in this server!", ephemeral=True)
        return
    last_match_ids = await async_get_last_match(puuid, 1)
    if last_match_ids and isinstance(last_match_ids, list) and len(last_match_ids) > 0:
        last_match_id = last_match_ids[0]
    else:
        await interaction.followup.send(f"No ranked matches found for {username}.", ephemeral=True)
        return
    rank_info = await asyncio.to_thread(get_summoner_rank, summoner_id)
    if rank_info == "Unknown":
        await interaction.followup.send(f"Unable to retrieve rank information for {username}.", ephemeral=True)
        return
    try:
        # Format attendu : "GOLD I 50 LP"
        rank_val, tier, lp_str, _ = rank_info.split()
        lp = int(lp_str)
    except Exception as e:
        logging.error(f"Error parsing rank info: {e}")
        await interaction.followup.send("Error parsing rank information.", ephemeral=True)
        return
    insert_player(summoner_id, puuid, username, guild_id, str(interaction.channel_id), last_match_id, tier, rank_val, lp)
    log_msg = f"User {username} registered in guild {guild_id} with rank {rank_val}, tier {tier} and LP {lp}."
    logging.info(log_msg)
    await interaction.followup.send(
        f"Player {username} successfully registered in this server with alert activated!\n"
        f"Rank: {rank_val}, Tier: {tier}, LP: {lp}, Last Match ID: {last_match_id}",
        ephemeral=True
    )

@tree.command(name="unregister", description="Unregister a player from this server")
@app_commands.autocomplete(username=username_autocomplete)
async def unregister(interaction: discord.Interaction, username: str):
    username = username.upper()
    guild_id = str(interaction.guild.id)
    player = get_player_by_username(username)
    if not player:
        await interaction.response.send_message("This player is not registered!", ephemeral=True)
        return
    puuid = player[1]
    if not get_player(puuid, guild_id):
        await interaction.response.send_message("This player is not registered in this server!", ephemeral=True)
        return
    delete_player(puuid, guild_id)
    await interaction.response.send_message(f"Player {username} has been unregistered from this server!", ephemeral=True)

@tree.command(name="rank", description="Display the rank of a registered player")
@app_commands.autocomplete(username=username_autocomplete)
async def rank(interaction: discord.Interaction, username: str):
    username = username.upper()
    guild_id = str(interaction.guild.id)
    player = get_player_by_username(username)
    if not player:
        await interaction.response.send_message(f"Player {username} is not registered.", ephemeral=True)
        return
    puuid = player[1]
    player_data = get_player(puuid, guild_id)
    if not player_data:
        await interaction.response.send_message(f"Player {username} is not registered in this server.", ephemeral=True)
        return
    tier = player_data[6]
    rank_val = player_data[7]
    lp = player_data[8]
    rank_message = f"**__Rank of {username}:__** {rank_val} {tier} {lp} LP"
    await interaction.response.send_message(rank_message)

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
    """
    Vérifie périodiquement si un joueur est en game.
    S'il l'est et qu'il n'a pas déjà été notifié, envoie un embed jaune et ajoute son puuid dans players_in_game.
    Lorsqu'il ne l'est plus, le retire afin de permettre une nouvelle notification lors d'une prochaine session.
    """
    global players_in_game
    while True:
        players = await async_get_all_players()
        for player in players:
            summoner_id, puuid, username, guild_id, channel_id, *_ = player
            channel = client.get_channel(int(channel_id))
            if not channel:
                continue
            in_game = await async_is_in_game(puuid)
            logging.info(f"Check in-game for {username}: {in_game}")
            if in_game:
                if puuid not in players_in_game:
                    embed = discord.Embed(
                        title="En game",
                        description=f"{username} est actuellement en game. Le suivi de son score débute.",
                        color=discord.Color.gold()
                    )
                    await channel.send(embed=embed)
                    players_in_game.add(puuid)
                    logging.info(f"Notification envoyée pour {username}")
            else:
                if puuid in players_in_game:
                    logging.info(f"{username} n'est plus en game, déblocage.")
                    players_in_game.remove(puuid)
        await asyncio.sleep(15)

async def check_for_game_completion():
    """
    Pour chaque joueur non en game, vérifie s'il a joué un nouveau match.
    Si un nouveau match est détecté, met à jour la base de données,
    envoie un embed (vert/rouge) avec les stats du match, et déclenche
    la mise à jour du leaderboard.
    """
    while True:
        players = await async_get_all_players()
        for player in players:
            summoner_id, puuid, username, guild_id, channel_id, last_match_id, old_tier, old_rank, old_lp, *_ = player
            channel = client.get_channel(int(channel_id))
            if not channel:
                continue
            # Ne traiter que si le joueur n'est pas en game
            if await async_is_in_game(puuid):
                continue
            current_matches = await async_get_last_match(puuid, 1)
            if not current_matches or not isinstance(current_matches, list):
                continue
            current_last_match_id = current_matches[0]
            if current_last_match_id != last_match_id:
                details = await async_get_match_details(current_last_match_id, puuid)
                if details:
                    result, champion, kills, deaths, assists, game_duration, champion_image, damage = details
                    new_rank_info = get_summoner_rank(summoner_id)
                    if new_rank_info != "Unknown":
                        try:
                            # Format attendu "GOLD I 50 LP"
                            rank_val, tier, new_lp_str, _ = new_rank_info.split()
                            new_lp = int(new_lp_str)
                        except Exception as e:
                            logging.error(f"Error parsing new rank info: {e}")
                            new_lp = 0
                        lp_change = calculate_lp_change(old_tier, old_rank, old_lp, tier, rank_val, new_lp)
                        update_player(puuid, guild_id, last_match_id=current_last_match_id,
                                      tier=tier, rank=rank_val, lp=new_lp, lp_24h=lp_change, lp_7d=lp_change)
                        await send_match_result_embed(
                            channel, username, result, kills, deaths, assists,
                            champion_image, lp_change, damage
                        )
                        leaderboard_update_event.set()
                        logging.info(f"Updated player {username}: LP change: {lp_change}, new LP: {new_lp}")
        await asyncio.sleep(15)


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
    # create_db()
    logging.info(f"Bot connected as {client.user}")
    # Lancement unique des tâches de fond
    asyncio.create_task(check_ingame())
    asyncio.create_task(check_for_game_completion())
    # Ne lancez pas notify_leaderboard_update

client.run(DISCORD_TOKEN)
