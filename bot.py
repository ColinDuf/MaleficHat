import discord
from discord import app_commands
import requests
import os
import logging
import asyncio
from datetime import timedelta
import pytz
import schedule
from dotenv import load_dotenv
from create_db import create_db
from fonction_bdd import (
    insert_player,
    insert_registration,
    get_registration,
    update_registration,
    delete_registration,
    insert_match,
    get_matches,
    insert_guild,
    get_guild,
    get_player,  # get_player(puuid)
    get_player_by_username,  # À ajouter dans fonction_bdd
    get_all_registrations, username_autocomplete  # Optionnel, pour check_for_game_completion
)

load_dotenv()
logging.basicConfig(level=logging.INFO)

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
RIOT_API_KEY = os.getenv('RIOT_API_KEY')

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# --- Fonctions d'accès à l'API Riot ---
def get_puuid(username, hashtag):
    """Récupère le PUUID à partir du nom d'utilisateur et du hashtag."""
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
    """Récupère l'ID du summoner à partir du PUUID."""
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
    """Récupère le rang (tier, rank et LP) du joueur."""
    url = f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        ranks = response.json()
        for rank in ranks:
            if rank['queueType'] == 'RANKED_SOLO_5x5':
                return f"{rank['tier']} {rank['rank']} {rank['leaguePoints']} LP"
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching summoner rank: {e}")
    return "Unknown"

def get_last_match(puuid, nb_last_match):
    """Récupère les derniers identifiants de match classé du joueur."""
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
    """Récupère les détails d'un match pour un joueur donné."""
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
                    # Exemple d'image en fonction du champion
                    if champion == "Naafiri":
                        champion_image = "https://media.discordapp.net/..."
                    elif champion == "Ambessa":
                        champion_image = "https://static.wikia.nocookie.net/..."
                    elif champion == "Aurora":
                        champion_image = "https://static.wikia.nocookie.net/..."
                    else:
                        champion_image = f"https://ddragon.leagueoflegends.com/cdn/13.1.1/img/champion/{champion}.png"
                    return result, champion, kills, deaths, assists, game_duration, champion_image, damage
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching match details: {e}")
    return None

def calculate_lp_change(old_tier, old_rank, old_lp, new_tier, new_rank, new_lp):
    tier_order = ['IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']
    rank_order = ['IV', 'III', 'II', 'I']
    if old_tier == new_tier:
        if old_rank == new_rank:
            return new_lp - old_lp
        else:
            return (rank_order.index(new_rank) - rank_order.index(old_rank)) * 100 + (new_lp - old_lp)
    else:
        tier_diff = (tier_order.index(new_tier) - tier_order.index(old_tier)) * 400
        rank_diff = (rank_order.index(new_rank) - rank_order.index(old_rank)) * 100
        return tier_diff + rank_diff + (new_lp - old_lp)

# --- Commandes du bot utilisant la BDD ---

@tree.command(name="register", description="Register a player in this server")
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
    puuid = get_puuid(riot_username, hashtag)
    if not puuid:
        await interaction.followup.send(f"Error fetching PUUID for {username}.", ephemeral=True)
        return
    summoner_id = get_summoner_id(puuid)
    if not summoner_id:
        await interaction.followup.send(f"Error fetching Summoner ID for {username}.", ephemeral=True)
        return
    # Vérifier si le joueur est déjà inscrit dans ce serveur
    if get_registration(puuid, guild_id):
        await interaction.followup.send(f"Player {username} is already registered in this server!", ephemeral=True)
        return
    last_match_ids = get_last_match(puuid, 1)
    if last_match_ids and isinstance(last_match_ids, list) and len(last_match_ids) > 0:
        last_match_id = last_match_ids[0]
    else:
        await interaction.followup.send(f"No ranked matches found for {username}.", ephemeral=True)
        return
    rank_info = get_summoner_rank(summoner_id)
    if rank_info == "Unknown":
        await interaction.followup.send(f"Unable to retrieve rank information for {username}.", ephemeral=True)
        return
    try:
        tier, rank_val, lp_str = rank_info.split()[:3]
        lp = int(lp_str)
    except Exception as e:
        logging.error(f"Error parsing rank info: {e}")
        await interaction.followup.send("Error parsing rank information.", ephemeral=True)
        return

    # Insertion dans la BDD
    insert_player(puuid, username, summoner_id)
    insert_registration(puuid, guild_id, str(interaction.channel_id), last_match_id, 0, tier, rank_val, lp)
    await interaction.followup.send(
        f"Player {username} successfully registered in this server!\n"
        f"Tier: {tier}, Rank: {rank_val}, LP: {lp}, Last Match ID: {last_match_id}",
        ephemeral=True
    )

@tree.command(name="unregister", description="Unregister a player from this server")
@app_commands.autocomplete(username=username_autocomplete)  # Pensez à adapter l'autocomplétion pour la BDD
async def unregister(interaction: discord.Interaction, username: str):
    username = username.upper()
    guild_id = str(interaction.guild.id)
    player = get_player_by_username(username)
    if not player:
        await interaction.response.send_message("This player is not registered!", ephemeral=True)
        return
    puuid = player[1]  # En supposant que la structure soit (summoner_id, puuid, username)
    if not get_registration(puuid, guild_id):
        await interaction.response.send_message("This player is not registered in this server!", ephemeral=True)
        return
    delete_registration(puuid, guild_id)
    await interaction.response.send_message(f"Player {username} has been unregistered from this server!", ephemeral=True)

@tree.command(name="rank", description="Affiche le rang d'un joueur enregistré")
@app_commands.autocomplete(username=username_autocomplete)
async def rank(interaction: discord.Interaction, username: str):
    username = username.upper()
    guild_id = str(interaction.guild.id)
    player = get_player_by_username(username)
    if not player:
        await interaction.response.send_message(f"Le joueur {username} n'est pas enregistré.", ephemeral=True)
        return
    puuid = player[1]
    reg = get_registration(puuid, guild_id)
    if not reg:
        await interaction.response.send_message(f"Le joueur {username} n'est pas enregistré dans ce serveur.", ephemeral=True)
        return
    # Structure de registration : (player_puuid, guild_id, channel_id, last_match_id, alerte, tier, rank, lp, lp_24h, lp_7d)
    tier = reg[5]
    rank_val = reg[6]
    lp = reg[7]
    rank_message = f"**__Rank of {username}:__** {tier} {rank_val} {lp} LP"
    await interaction.response.send_message(rank_message)

@tree.command(name="career", description="Displays a player's last 10 ranked Solo/Duo games")
@app_commands.autocomplete(username=username_autocomplete)
async def lastmatches(interaction: discord.Interaction, username: str):
    username = username.upper()
    await interaction.response.defer()
    player = get_player_by_username(username)
    if not player:
        await interaction.followup.send("This player is not registered!", ephemeral=True)
        return
    puuid = player[1]
    summoner_id = player[0]  # Structure : (summoner_id, puuid, username)
    rank_info = get_summoner_rank(summoner_id)
    if rank_info == "Unknown":
        await interaction.followup.send("Error retrieving player rank information!", ephemeral=True)
        return
    match_ids = get_last_match(puuid, 10)
    if not match_ids or not isinstance(match_ids, list):
        await interaction.followup.send("Error retrieving match data or no matches found!", ephemeral=True)
        return
    match_results = []
    for match_id in match_ids:
        details = get_match_details(match_id, puuid)
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
            value=(
                f"**Champion:** {match['champion']}\n"
                f"**K/D/A:** {match['kda']}\n"
                f"**Damage:** {match['damage']}\n"
                f"**Duration:** {match['duration']}\n"
            ),
        )
        if (i + 1) % 2 == 0:
            embed.add_field(name='\u200b', value='\u200b', inline=True)
    await interaction.followup.send(embed=embed)

@tree.command(name="alerte", description="At the end of a player's game, the statistics are sent automatically")
@app_commands.autocomplete(username=username_autocomplete)
async def alerte(interaction: discord.Interaction, username: str):
    username = username.upper()
    await interaction.response.defer()
    guild_id = str(interaction.guild.id)
    player = get_player_by_username(username)
    if not player:
        await interaction.followup.send("This player is not registered!", ephemeral=True)
        return
    puuid = player[1]
    reg = get_registration(puuid, guild_id)
    if not reg:
        await interaction.followup.send("This player is not registered in this server!", ephemeral=True)
        return
    summoner_id = player[0]
    rank_info = get_summoner_rank(summoner_id)
    if rank_info != "Unknown":
        try:
            tier, rank_val, lp_str = rank_info.split()[:3]
            lp = int(lp_str)
        except Exception as e:
            logging.error(f"Error parsing rank info: {e}")
            lp = 0
        update_registration(puuid, guild_id, alerte=True, tier=tier, rank=rank_val, lp=lp)
        await interaction.followup.send(f"Alerte activée pour {username} sur ce channel", ephemeral=True)
    else:
        await interaction.followup.send("Could not retrieve the player's rank.", ephemeral=True)

# --- Fonctions pour le leaderboard et la vérification des matchs ---
async def update_leaderboard_message(channel: discord.TextChannel):
    guild_id = str(channel.guild.id)
    # Récupérer les infos du leaderboard via une requête SQL
    import sqlite3
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.username, r.tier, r.rank, r.lp_24h, r.lp_7d
        FROM registrations r
        JOIN players p ON r.player_puuid = p.puuid
        WHERE r.guild_id = ?
    """, (guild_id,))
    rows = cursor.fetchall()
    conn.close()
    leaderboard_message = "Leaderboard\n\nPseudo | Rank | LP (24h) | LP (7j)\n----------------------------------\n"
    for row in rows:
        username, tier, rank_val, lp_24h, lp_7d = row
        leaderboard_message += f"{username} | {tier} {rank_val} | {lp_24h} | {lp_7d}\n"
    async for message in channel.history(limit=50):
        if message.author == client.user and message.embeds and "Leaderboard" in message.embeds[0].title:
            await message.edit(content=f"```{leaderboard_message}```")
            return
    await channel.send(f"```{leaderboard_message}```")

async def update_leaderboard_embed(guild_id):
    # Récupérer les données du leaderboard en effectuant une jointure entre registrations et players
    guild_data = get_guild(guild_id)
    if not guild_data:
        logging.warning(f"No guild data for guild {guild_id}")
        return
    leaderboard_channel_id = guild_data[1]
    channel = client.get_channel(int(leaderboard_channel_id))
    if not channel:
        logging.warning(f"Leaderboard channel {leaderboard_channel_id} not found")
        return
    import sqlite3
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.username, r.tier, r.rank, r.lp_24h, r.lp_7d
        FROM registrations r
        JOIN players p ON r.player_puuid = p.puuid
        WHERE r.guild_id = ?
    """, (guild_id,))
    rows = cursor.fetchall()
    conn.close()
    embed = discord.Embed(
        title="Leaderboard",
        description="Classement des joueurs",
        color=discord.Color.blue()
    )
    for row in rows:
        username, tier, rank_val, lp_24h, lp_7d = row
        embed.add_field(
            name=username,
            value=f"Rank: {tier} {rank_val}\nLP (24h): {lp_24h}\nLP (7j): {lp_7d}",
            inline=False
        )
    async for message in channel.history(limit=50):
        if message.author == client.user and message.embeds and "Leaderboard" in message.embeds[0].title:
            await message.edit(embed=embed)
            return
    await channel.send(embed=embed)

async def check_for_game_completion():
    processed_matches = set()
    while True:
        # Récupérer toutes les inscriptions de la BDD
        import sqlite3
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.player_puuid, r.guild_id, r.channel_id, r.last_match_id, r.tier, r.rank, r.lp, p.summoner_id, p.username
            FROM registrations r
            JOIN players p ON r.player_puuid = p.puuid
        """)
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            player_puuid, guild_id, channel_id, last_match_id, old_tier, old_rank, old_lp, summoner_id, username = row
            channel = client.get_channel(int(channel_id))
            if not channel:
                continue
            current_last_match_ids = get_last_match(player_puuid, 1)
            if not current_last_match_ids or not isinstance(current_last_match_ids, list):
                continue
            current_last_match_id = current_last_match_ids[0]
            if current_last_match_id in processed_matches:
                continue
            if current_last_match_id != last_match_id:
                details = get_match_details(current_last_match_id, player_puuid)
                if details:
                    result, champion, kills, deaths, assists, game_duration, champion_image, damage = details
                    new_rank_info = get_summoner_rank(summoner_id)
                    if new_rank_info != "Unknown":
                        try:
                            new_tier, new_rank, new_lp_str = new_rank_info.split()[:3]
                            new_lp = int(new_lp_str)
                        except Exception as e:
                            logging.error(f"Error parsing new rank info: {e}")
                            new_lp = 0
                        lp_change = calculate_lp_change(old_tier, old_rank, old_lp, new_tier, new_rank, new_lp)
                        update_registration(player_puuid, guild_id, last_match_id=current_last_match_id,
                                            tier=new_tier, rank=new_rank, lp=new_lp,
                                            lp_24h=lp_change, lp_7d=lp_change)
                        await send_match_result_embed(
                            channel, username, result, champion, kills, deaths, assists,
                            game_duration, champion_image, lp_change, damage
                        )
                        await update_leaderboard_embed(guild_id)
                        logging.info(f"Updated player {username}: LP change: {lp_change}, new LP: {new_lp}")
                        processed_matches.add(current_last_match_id)
        await asyncio.sleep(5)

async def send_match_result_embed(channel, username, result, champion, kills, deaths, assists,
                                  game_duration, champion_image, lp_change, damage):
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
    asyncio.create_task(check_for_game_completion())
    # scheduler_loop = schedule_resets()  # Pensez à adapter schedule_resets si nécessaire
    # asyncio.create_task(scheduler_loop())

client.run(DISCORD_TOKEN)
