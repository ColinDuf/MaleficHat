import discord
from discord import app_commands
import requests
import json
import os
from datetime import timedelta
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

# Configuration des logs
logging.basicConfig(level=logging.INFO)

# Récupérer les tokens via des variables d'environnement
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
RIOT_API_KEY = os.getenv('RIOT_API_KEY')

# Créer une instance de bot avec les intents nécessaires
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Fichier JSON unique pour stocker toutes les informations
DATA_FILE = 'data.json'

# Fonction pour charger les pseudos enregistrés dans data.json
def load_registered_usernames():
    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
            return list(data.keys())  # Renvoie une liste des usernames
    except FileNotFoundError:
        return []

# Fonctions pour charger et sauvegarder les données JSON
def load_data():
    """Charge les données depuis un fichier JSON unique."""
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r') as file:
        return json.load(file)

def save_data(data):
    """Enregistre les données dans un fichier JSON unique."""
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

# Vos fonctions pour récupérer les PUUIDs, IDs, matchs, etc.
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
    """Récupère le rang du joueur en utilisant son summoner ID."""
    url = f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        ranks = response.json()
        # Rechercher le rang classé Solo/Duo
        for rank in ranks:
            if rank['queueType'] == 'RANKED_SOLO_5x5':
                return f"{rank['tier']} {rank['rank']} {rank['leaguePoints']} LP"
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching summoner rank: {e}")
    return "Unknown"



def get_last_match(puuid):
    """Récupère l'identifiant des dernières parties classées d'un joueur."""
    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?type=ranked&count=1"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()[0] if response.json() else None  # Retourne le dernier match
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching last match: {e}")
        return None

def get_match_details(match_id, puuid):
    """Récupère les détails d'un match en utilisant son ID."""
    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        match_data = response.json()
        game_mode = match_data['info']['queueId']
        if game_mode == 420:  # Ranked Solo/Duo
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
                    # Vérification du personnage pour définir une image spécifique
                    if champion == "Naafiri":   
                        champion_image = "https://media.discordapp.net/attachments/1287134099026481243/1287206571394207764/Naafiri_OriginalSquare.png?ex=66f0b409&is=66ef6289&hm=862f77b8b4278e07b144b8a3869b4fa7df654cd485c9454eaf250a9895a86011&=&format=webp&quality=lossless"
                    else:
                    # Utilisation de l'image par défaut pour les autres champions
                        champion_image = f"https://ddragon.leagueoflegends.com/cdn/13.1.1/img/champion/{champion}.png"
                        
                    return result, champion, kills, deaths, assists, game_duration, champion_image, damage
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching match details: {e}")
    return None

async def check_for_game_completion():
    while True:
        data = load_data()
        for username, user_data in data.items():
            puuid = user_data.get('puuid')
            channel_id = user_data.get('channel_id')
            last_match_id = user_data.get('last_match_id')

            if not puuid or not channel_id:
                continue

            channel = client.get_channel(channel_id)
            if not channel:
                continue

            current_last_match_id = get_last_match(puuid)
            if not current_last_match_id:
                continue

            if current_last_match_id != last_match_id:
                # Match terminé
                match_details = get_match_details(current_last_match_id, puuid)
                if match_details:
                    result, champion, kills, deaths, assists, game_duration, champion_image, damage = match_details
                    
                    # Récupérer le nouveau rang du joueur
                    summoner_id = user_data['summoner_id']
                    new_rank_info = get_summoner_rank(summoner_id)
                    if new_rank_info != "Unknown":
                        new_tier, new_rank, new_lp = new_rank_info.split()[:3]
                        new_lp = int(new_lp.split()[0])

                        # Comparer avec le rang précédent
                        old_tier = user_data['tier']
                        old_rank = user_data['rank']
                        old_lp = user_data['lp']

                        lp_change = calculate_lp_change(old_tier, old_rank, old_lp, new_tier, new_rank, new_lp)
                        
                        # Mettre à jour les nouvelles informations dans data.json
                        data[username]['tier'] = new_tier
                        data[username]['rank'] = new_rank
                        data[username]['lp'] = new_lp
                        save_data(data)

                        # Construire l'embed pour le match terminé avec les changements de LP
                        if result == ':green_circle:':
                            game_result = "Victory"
                        else:
                            game_result = "Defeat"

                        # Construire l'embed pour le match terminé avec les changements de LP
                        lp_text = "LP Win" if result == ':green_circle:' else "LP Lost"
                        embed = discord.Embed(
                            title=f"{game_result} for {username}",
                            color=discord.Color.green() if result == ':green_circle:' else discord.Color.red()
                        )
                        embed.add_field(name="K/D/A", value=f"{kills}/{deaths}/{assists}", inline=True)
                        embed.add_field(name="Damage", value=f"{damage}", inline=True)
                        embed.add_field(name=lp_text, value=f"{'+' if lp_change > 0 else ''}{lp_change} LP", inline=True)
                        embed.set_thumbnail(url=champion_image)

                        await channel.send(embed=embed)
                
                # Mettre à jour le last_match_id
                data[username]['last_match_id'] = current_last_match_id
                save_data(data)

        await asyncio.sleep(30)

def calculate_lp_change(old_tier, old_rank, old_lp, new_tier, new_rank, new_lp):
    tier_order = ['IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']
    rank_order = ['IV', 'III', 'II', 'I']

    if old_tier == new_tier:
        # Même tier, juste comparer les LP et la division
        if old_rank == new_rank:
            return new_lp - old_lp
        else:
            return (rank_order.index(new_rank) - rank_order.index(old_rank)) * 100 + (new_lp - old_lp)
    else:
        # Tier différent, calculer le changement de tier
        tier_diff = (tier_order.index(new_tier) - tier_order.index(old_tier)) * 400  # Chaque tier a environ 400 LP
        rank_diff = (rank_order.index(new_rank) - rank_order.index(old_rank)) * 100
        return tier_diff + rank_diff + (new_lp - old_lp)


# Commande pour ajouter un joueur
@tree.command(name="register", description="Add a player with his Riot ID")
@app_commands.describe(username="GameName", hashtag="#")
async def addplayer(interaction: discord.Interaction, username: str, hashtag: str):
    username = username.upper()
    hashtag = hashtag.upper()

    # Charger les données existantes
    data = load_data()

    # Vérifier si le joueur est déjà inscrit
    player_key = f"{username}#{hashtag}"
    if player_key in data:
        await interaction.response.send_message("This player is already registered!", ephemeral=True)
        return

    # Récupérer le PUUID / SUMMONER ID via l'API de Riot
    puuid = get_puuid(username, hashtag)
    summoner_id = get_summoner_id(puuid)

    # Stocker les informations du joueur dans le fichier data.json
    data[player_key] = {
        'puuid': puuid,
        'summoner_id': summoner_id,
        'channel_id': None,
        'last_match_id': None
    }
    save_data(data)

    await interaction.response.send_message(f"Player {player_key} added successfully!", ephemeral=True)

# Autocomplétion pour les pseudos
async def username_autocomplete(interaction: discord.Interaction, current: str):
    usernames = load_registered_usernames()
    return [app_commands.Choice(name=username, value=username) for username in usernames if current.lower() in username.lower()]

def get_last_matches(puuid, count=5):
    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?type=ranked&count={count}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching match IDs: {e}")
        return None

@tree.command(name="career", description="Displays a player's last 5 ranked Solo/Duo games")
@app_commands.autocomplete(username=username_autocomplete)
async def lastmatches(interaction: discord.Interaction, username: str):
    username = username.upper()

    await interaction.response.defer()

    data = load_data()

    if username not in data:
        await interaction.followup.send("This player is not registered!")
        return

    puuid = data[username]['puuid']
    match_ids = get_last_matches(puuid, count=5)  # Récupérer les 5 derniers matchs

    if not match_ids:
        await interaction.followup.send("Error retrieving match data or no matches found!")
        return

    embed = discord.Embed(
        title=f"Last 5 Ranked Matches for {username}",
        description="Here are the details of the last 5 ranked games:",
        color=discord.Color.blue()
    )

    for i, match_id in enumerate(match_ids[:5], start=1):
        match_details = get_match_details(match_id, puuid)
        if match_details:
            result, champion, kills, deaths, assists, game_duration, _, damage = match_details
            embed.add_field(
                name=f"Match {i}",
                value=(f"**Champion**: {champion}\n"
                       f"**K/D/A**: {kills}/{deaths}/{assists}\n"
                       f"**Damage Dealt**: {damage}\n"
                       f"**Game Duration**: {game_duration}\n"
                       f"**Result**: {result}"),
                inline=False
            )

    await interaction.followup.send(embed=embed)


@tree.command(name="alerte", description="At the end of a player's game, the statistics are sent automatically")
@app_commands.autocomplete(username=username_autocomplete)
async def alerte(interaction: discord.Interaction, username: str):
    username = username.upper()

    await interaction.response.defer()

    data = load_data()

    if username not in data:
        await interaction.followup.send("This player is not registered!")
        return

    # Récupérer le PUUID et le summoner ID
    puuid = data[username]['puuid']
    summoner_id = data[username]['summoner_id']
    
    # Récupérer le rang du joueur
    rank_info = get_summoner_rank(summoner_id)
    if rank_info != "Unknown":
        # Enregistrer les détails du rang
        tier, rank, lp = rank_info.split()[:3]
        lp = int(lp.split()[0])  # Extraire les LP sous forme d'entier

        # Stocker l'ID du channel et les informations du rang dans les données
        data[username]['channel_id'] = interaction.channel_id
        data[username]['tier'] = tier
        data[username]['rank'] = rank
        data[username]['lp'] = lp
    else:
        await interaction.followup.send("Could not retrieve the player's rank.")

    save_data(data)
    await interaction.followup.send(f"Alerte activée pour {username} sur ce channel")



@client.event
async def on_ready():
    await tree.sync()
    logging.info(f"Bot connected as {client.user}")
    asyncio.create_task(check_for_game_completion())

# Démarrer le bot
client.run(DISCORD_TOKEN)