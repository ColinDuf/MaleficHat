import discord
from discord import app_commands
import requests
import json
import os
from datetime import timedelta, datetime
import asyncio
import logging
from dotenv import load_dotenv

lock = asyncio.Lock()
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
    logging.info("Saving data to data.json")
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)


async def username_autocomplete(interaction: discord.Interaction, current: str):
    data = load_data()  # Charger les données
    guild_id = str(interaction.guild.id)  # ID du serveur actuel (converti en string pour correspondre à la structure des données)
    
    # Filtrer les joueurs par ceux qui sont enregistrés dans ce serveur
    usernames = []
    for player_key, player_data in data.items():
        if guild_id in player_data.get('guilds', {}):  # Vérifier si le joueur est enregistré dans ce serveur
            usernames.append(player_key)
    
    # Filtrer les résultats pour ne proposer que ceux qui correspondent au texte de l'utilisateur
    return [
        app_commands.Choice(name=username, value=username)
        for username in usernames if current.lower() in username.lower()
    ]

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
    """Fetches the player's rank, tier, and LP."""
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
    """Fetches the most recent ranked match IDs for the player."""
    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?type=ranked&count={nb_last_match}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        matches = response.json()
        
        # Vérifiez si matches est une liste et qu'elle n'est pas vide
        if isinstance(matches, list) and matches:
            return matches  # Return the match IDs as a list of strings
        return None  # Return None if no matches found

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching last matches: {e}")
        return None

def get_match_details(match_id, puuid):
    """Récupère les détails d'un match en utilisant son ID."""
    if not match_id:  # Vérifier si match_id est valide
        logging.error("No match ID provided.")
        return None

    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP
        
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
                    elif champion == "Ambessa":   
                        champion_image = "https://static.wikia.nocookie.net/lolesports_gamepedia_en/images/6/65/AmbessaSquare.png/revision/latest?cb=20241105211540"
                    elif champion == "Aurora":   
                        champion_image = "https://static.wikia.nocookie.net/lolesports_gamepedia_en/images/9/9d/AuroraSquare.png/revision/latest?cb=20241215182230"
                    else:
                        champion_image = f"https://ddragon.leagueoflegends.com/cdn/13.1.1/img/champion/{champion}.png"
                        
                    return result, champion, kills, deaths, assists, game_duration, champion_image, damage
                    
    except requests.exceptions.HTTPError as http_err:
        if response.status_code == 404:
            logging.error(f"Match ID {match_id} not found.")
        else:
            logging.error(f"HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching match details: {e}")
    
    return None

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






@tree.command(name="register", description="Register a player in this server")
@app_commands.describe(gamename="The player's Riot in game name", tagline="The player's #")
async def register(interaction: discord.Interaction, gamename: str, tagline: str):
    await interaction.response.defer(ephemeral=True)  # This prevents timeout issues
    
    username = gamename.upper() + "#" + tagline.upper()  # Utilise "#" comme séparateur

    guild_id = str(interaction.guild.id)  # Convert guild ID to string
    data = load_data()  # Load existing data from data.json

    # Check if the player is already registered in this guild
    if username in data and guild_id in data[username]['guilds']:
        await interaction.followup.send(f"Player {username} is already registered in this server!", ephemeral=True)
        return

    # Split username and hashtag
    try:
        riot_username, hashtag = username.split('#')
    except ValueError:
        await interaction.followup.send(f"Invalid username format. Use USERNAME#HASHTAG.", ephemeral=True)
        return

    # Fetch PUUID and Summoner ID
    puuid = get_puuid(riot_username, hashtag)
    if not puuid:
        await interaction.followup.send(f"Error fetching PUUID for {username}.", ephemeral=True)
        return

    summoner_id = get_summoner_id(puuid)
    if not summoner_id:
        await interaction.followup.send(f"Error fetching Summoner ID for {username}.", ephemeral=True)
        return

    # Add player to the data structure if not already present
    if username not in data:
        data[username] = {
            "puuid": puuid,
            "summoner_id": summoner_id,
            "guilds": {}
        }

    # Get the last match ID
    last_match_id = get_last_match(puuid, 1)
    if last_match_id and isinstance(last_match_id, list) and len(last_match_id) > 0:
        last_match_id = last_match_id[0]
    else:
        await interaction.followup.send(f"No ranked matches found for {username}.", ephemeral=True)
        return

    rank_info = get_summoner_rank(summoner_id)
    if rank_info == "Unknown":
        await interaction.followup.send(f"Unable to retrieve rank information for {username}.", ephemeral=True)
        return

    tier, rank, lp = rank_info.split()[:3]
    lp = int(lp.split()[0])

    data[username]['guilds'][guild_id] = {
        "channel_id": interaction.channel_id,
        "last_match_id": last_match_id,
        "alerte": False,
        "tier": tier,
        "rank": rank,
        "lp": lp
    }

    save_data(data)

    await interaction.followup.send(
        f"Player {username} successfully registered in this server!\n"
        f"Tier: {tier}, Rank: {rank}, LP: {lp}, Last Match ID: {last_match_id}", 
        ephemeral=True
    )

@tree.command(name="unregister", description="Unregister a player from this server")
@app_commands.autocomplete(username=username_autocomplete)
async def unregister(interaction: discord.Interaction, username: str):
    username = username.upper()  # S'assurer que le username est en majuscules comme dans data.json
    guild_id = str(interaction.guild.id)  # ID du serveur actuel (converti en string)

    # Charger les données existantes
    data = load_data()

    # Log du guild_id et du username
    logging.info(f"Unregister command initiated for guild_id: {guild_id}, username: {username}")

    # Vérifier si le joueur est enregistré dans le fichier data.json
    player_key = None
    for key, player_data in data.items():
        # Assurer que le joueur correspond à 'username#hashtag' et est dans le bon serveur (guild_id)
        if key == username and guild_id in player_data.get('guilds', {}):
            player_key = key
            logging.info(f"Player {player_key} found in guild {guild_id}")
            break
        else:
            logging.info(f"Checking player key: {key}, no match for {username} in guild {guild_id}")

    # Si le joueur n'a pas été trouvé dans ce serveur
    if not player_key:
        logging.warning(f"Player {username} not found in guild {guild_id}")
        await interaction.response.send_message("This player is not registered in this server!", ephemeral=True)
        return

    # Supprimer uniquement les informations du joueur pour ce serveur (guild_id)
    del data[player_key]['guilds'][guild_id]
    logging.info(f"Removed player {player_key} from guild {guild_id}")

    # Si le joueur n'est plus enregistré dans aucun serveur, supprimer complètement l'entrée
    if not data[player_key]['guilds']:  # Vérifier si la section 'guilds' est vide
        logging.info(f"No more guilds for player {player_key}, removing player entirely")
        del data[player_key]  # Supprimer l'entrée complète si aucune guild n'est enregistrée

    # Sauvegarder les modifications dans le fichier data.json
    save_data(data)

    await interaction.response.send_message(f"Player {player_key} has been unregistered from this server!", ephemeral=True)

@tree.command(name="career", description="Displays a player's last 10 ranked Solo/Duo games")
@app_commands.autocomplete(username=username_autocomplete)
async def lastmatches(interaction: discord.Interaction, username: str):
    username = username.upper()  # Convertir le nom d'utilisateur en majuscules

    await interaction.response.defer()  # Déférer la réponse pour signaler une attente

    data = load_data()  # Charger les données des joueurs

    # Vérifier si le joueur est enregistré
    if username not in data:
        await interaction.followup.send("This player is not registered!")
        return

    # Récupérer les informations du joueur
    puuid = data[username]['puuid']
    summoner_id = data[username]['summoner_id']

    # Récupérer le rang (tier, rank) et les LP du joueur
    rank_info = get_summoner_rank(summoner_id)
    if rank_info == "Unknown":
        await interaction.followup.send("Error retrieving player rank information!")
        return

    # Récupérer les 10 derniers matchs
    match_ids = get_last_match(puuid, 10)

    if not match_ids or not isinstance(match_ids, list):
        await interaction.followup.send("Error retrieving match data or no matches found!")
        return

    # Récupérer les détails de chaque match
    match_results = []
    for match_id in match_ids:
        match_details = get_match_details(match_id, puuid)

        if match_details:
            result, champion, kills, deaths, assists, game_duration, champion_image, damage = match_details
            match_results.append({
                "result": result,
                "champion": champion,
                "kda": f"{kills}/{deaths}/{assists}",
                "damage": damage,
                "duration": game_duration,
                "champion_image": champion_image
            })

    if not match_results:
        await interaction.followup.send("No match details found for the player's last 10 games.")
        return

    # Construire l'embed
    embed = discord.Embed(
        title=f"Last 10 Ranked Matches for {username}",
        description=f"Rank: {rank_info}",
        color=discord.Color.blue()
    )

    # Ajout des informations des matchs dans deux colonnes
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

        # Pour garantir qu'il y a bien deux colonnes par ligne
        if (i + 1) % 2 == 0:
            embed.add_field(name='\u200b', value='\u200b', inline=True)

    # Envoyer l'embed
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

    # Vérifier si le joueur est inscrit dans ce serveur
    guild_id = str(interaction.guild.id)
    if guild_id not in data[username]['guilds']:
        await interaction.followup.send("This player is not registered in this server!")
        return

    # Récupérer les données du joueur pour ce serveur
    player_data = data[username]['guilds'][guild_id]
    
    # Récupérer le PUUID et le summoner ID
    summoner_id = data[username]['summoner_id']
    
    # Récupérer le rang du joueur
    rank_info = get_summoner_rank(summoner_id)
    if rank_info != "Unknown":
        # Enregistrer les détails du rang
        tier, rank, lp = rank_info.split()[:3]
        lp = int(lp.split()[0])  # Extraire les LP sous forme d'entier

        # Stocker les informations du rang et activer l'alerte
        player_data['alerte'] = True
        player_data['tier'] = tier
        player_data['rank'] = rank
        player_data['lp'] = lp
    else:
        await interaction.followup.send("Could not retrieve the player's rank.")

    save_data(data)
    await interaction.followup.send(f"Alerte activée pour {username} sur ce channel")











# Autocomplétion des salons Discord
async def channel_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=channel.name, value=str(channel.id))
        for channel in interaction.guild.text_channels
        if current.lower() in channel.name.lower()
    ]

# Autocomplétion des joueurs dans le leaderboard
async def leaderboard_users_autocomplete(interaction: discord.Interaction, current: str):
    data = load_data()
    guild_id = str(interaction.guild.id)
    leaderboard_users = data.get("leaderboards", {}).get(guild_id, {}).get("players", [])
    return [
        app_commands.Choice(name=user, value=user)
        for user in leaderboard_users if current.lower() in user.lower()
    ]

# Fonction existante pour l'autocomplétion des utilisateurs enregistrés
async def username_autocomplete(interaction: discord.Interaction, current: str):
    data = load_data()  # Charger les données
    guild_id = str(interaction.guild.id)  # ID du serveur actuel (converti en string pour correspondre à la structure des données)
    
    # Filtrer les joueurs par ceux qui sont enregistrés dans ce serveur
    usernames = []
    for player_key, player_data in data.items():
        if guild_id in player_data.get('guilds', {}):  # Vérifier si le joueur est enregistré dans ce serveur
            usernames.append(player_key)
    
    # Filtrer les résultats pour ne proposer que ceux qui correspondent au texte de l'utilisateur
    return [
        app_commands.Choice(name=username, value=username)
        for username in usernames if current.lower() in username.lower()
    ]

# Mettre à jour ou créer le message du leaderboard
async def update_leaderboard_message(channel: discord.TextChannel):
    data = load_data()
    guild_id = str(channel.guild.id)
    leaderboard_data = data.get("leaderboards", {}).get(guild_id, {}).get("players", [])
    
    leaderboard_message = "Leaderboard\n\n"
    leaderboard_message += "Pseudo | Rank | LP (24h) | LP (7j)\n"
    leaderboard_message += "----------------------------------\n"

    for puuid in leaderboard_data:
        player_data = next((pdata for pname, pdata in data.items() if pdata.get("puuid") == puuid), None)
        if player_data:
            username = player_data.get("guilds", {}).get(guild_id, {}).get("username", "Unknown")
            rank = f"{player_data['guilds'][guild_id]['tier']} {player_data['guilds'][guild_id]['rank']}"
            lp_24h = player_data['guilds'][guild_id].get("lp_24h", 0)
            lp_7d = player_data['guilds'][guild_id].get("lp_7d", 0)
            leaderboard_message += f"{username} | {rank} | {lp_24h} | {lp_7d}\n"

    async for message in channel.history(limit=50):
        if message.author == client.user and message.content.startswith("Leaderboard"):
            await message.edit(content=f"```{leaderboard_message}```")
            return

    # Si aucun message existant n'est trouvé, créer un nouveau message
    await channel.send(f"```{leaderboard_message}```")

# Vérifier les parties terminées et mettre à jour le leaderboard
async def check_for_game_completion():
    processed_matches = set()  # Pour stocker les matchs déjà traités

    while True:
        async with lock:
            data = load_data()

            # Vérifier les joueurs suivis par le système d'alerte
            for username, user_data in data.items():
                puuid = user_data.get('puuid')
                for guild_id, guild_data in user_data.get('guilds', {}).items():
                    channel_id = guild_data.get('channel_id')
                    last_match_id = guild_data.get('last_match_id')

                    if not puuid or not channel_id:
                        continue

                    channel = client.get_channel(channel_id)
                    if not channel:
                        continue

                    current_last_match_id = get_last_match(puuid, 1)
                    if not current_last_match_id or not isinstance(current_last_match_id, list):
                        continue

                    current_last_match_id = current_last_match_id[0]

                    if current_last_match_id in processed_matches:
                        continue

                    if current_last_match_id != last_match_id:
                        match_details = get_match_details(current_last_match_id, puuid)
                        if match_details:
                            result, champion, kills, deaths, assists, game_duration, champion_image, damage = match_details
                            summoner_id = user_data['summoner_id']
                            new_rank_info = get_summoner_rank(summoner_id)
                            if new_rank_info != "Unknown":
                                new_tier, new_rank, new_lp = new_rank_info.split()[:3]
                                new_lp = int(new_lp.split()[0])

                                # Comparer avec les anciennes données et mettre à jour
                                old_tier = guild_data['tier']
                                old_rank = guild_data['rank']
                                old_lp = guild_data['lp']
                                lp_change = calculate_lp_change(old_tier, old_rank, old_lp, new_tier, new_rank, new_lp)

                                guild_data['tier'] = new_tier
                                guild_data['rank'] = new_rank
                                guild_data['lp'] = new_lp
                                guild_data['lp_24h'] = guild_data.get('lp_24h', 0) + lp_change
                                guild_data['lp_7d'] = guild_data.get('lp_7d', 0) + lp_change
                                guild_data['last_match_id'] = current_last_match_id

                                save_data(data)

                                # Mettre à jour le leaderboard
                                leaderboard = data.get("leaderboards", {}).get(guild_id, {})
                                leaderboard_channel = client.get_channel(leaderboard.get("channel_id"))
                                if leaderboard_channel:
                                    await update_leaderboard_message(leaderboard_channel)

                                logging.info(f"Updated player {username}: LP change: {lp_change}, new LP: {new_lp}")

                                processed_matches.add(current_last_match_id)

        await asyncio.sleep(5)


















@client.event
async def on_ready():
    await tree.sync()
    logging.info(f"Bot connected as {client.user}")
    asyncio.create_task(check_for_game_completion())

# Démarrer le bot
client.run(DISCORD_TOKEN)