import sqlite3

import discord
from discord import app_commands

DB_PATH = "database.db"


def get_connection():
    """
    Retourne une connexion à la base de données SQLite.
    """
    return sqlite3.connect(DB_PATH)


# ----- Opérations sur la table players -----

def insert_player(puuid, username, summoner_id):
    """
    Insère un nouveau joueur dans la table players si il n'existe pas déjà.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players WHERE puuid = ?", (puuid,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO players (puuid, username, summoner_id) VALUES (?, ?, ?)",
            (puuid, username, summoner_id)
        )
        conn.commit()
    conn.close()


def get_player(puuid):
    """
    Récupère les informations d'un joueur à partir de son puuid.
    Retourne un tuple (summoner_id, puuid, username) ou None si non trouvé.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players WHERE puuid = ?", (puuid,))
    player = cursor.fetchone()
    conn.close()
    return player


def get_player_by_username(username):
    """
    Récupère les informations d'un joueur à partir de son username.
    Retourne un tuple (summoner_id, puuid, username) ou None si non trouvé.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players WHERE username = ?", (username,))
    player = cursor.fetchone()
    conn.close()
    return player


# ----- Opérations sur la table registrations -----

def insert_registration(player_puuid, guild_id, channel_id, last_match_id,
                        alerte, tier, rank, lp, lp_24h=0, lp_7d=0):
    """
    Insère une inscription (registration) reliant un joueur à un serveur (guild).
    Le couple (player_puuid, guild_id) est unique.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registrations WHERE player_puuid = ? AND guild_id = ?",
                   (player_puuid, guild_id))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO registrations 
            (player_puuid, guild_id, channel_id, last_match_id, alerte, tier, rank, lp, lp_24h, lp_7d)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (player_puuid, guild_id, channel_id, last_match_id, alerte, tier, rank, lp, lp_24h, lp_7d))
        conn.commit()
    conn.close()


def get_registration(player_puuid, guild_id):
    """
    Récupère une inscription pour un joueur donné dans un serveur précis.
    Retourne un tuple correspondant ou None sinon trouve.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registrations WHERE player_puuid = ? AND guild_id = ?",
                   (player_puuid, guild_id))
    registration = cursor.fetchone()
    conn.close()
    return registration


async def username_autocomplete(interaction: discord.Interaction, current: str):
    import sqlite3
    guild_id = str(interaction.guild.id)

    # Connexion à la base de données et récupération des usernames enregistrés dans ce serveur
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.username
        FROM players p
        JOIN registrations r ON p.puuid = r.player_puuid
        WHERE r.guild_id = ?
    """, (guild_id,))
    rows = cursor.fetchall()
    conn.close()

    usernames = [row[0] for row in rows]

    # Filtrer les résultats pour ne proposer que ceux correspondant au texte saisi
    return [
        app_commands.Choice(name=username, value=username)
        for username in usernames if current.lower() in username.lower()
    ]


def update_registration(player_puuid, guild_id, channel_id=None, last_match_id=None,
                        alerte=None, tier=None, rank=None, lp=None, lp_24h=None, lp_7d=None):
    """
    Met à jour les informations d'une inscription.
    Seules les valeurs non-None seront mises à jour.
    """
    conn = get_connection()
    cursor = conn.cursor()

    updates = []
    params = []
    if channel_id is not None:
        updates.append("channel_id = ?")
        params.append(channel_id)
    if last_match_id is not None:
        updates.append("last_match_id = ?")
        params.append(last_match_id)
    if alerte is not None:
        updates.append("alerte = ?")
        params.append(alerte)
    if tier is not None:
        updates.append("tier = ?")
        params.append(tier)
    if rank is not None:
        updates.append("rank = ?")
        params.append(rank)
    if lp is not None:
        updates.append("lp = ?")
        params.append(lp)
    if lp_24h is not None:
        updates.append("lp_24h = ?")
        params.append(lp_24h)
    if lp_7d is not None:
        updates.append("lp_7d = ?")
        params.append(lp_7d)

    if updates:
        params.extend([player_puuid, guild_id])
        query = "UPDATE registrations SET " + ", ".join(updates) + " WHERE player_puuid = ? AND guild_id = ?"
        cursor.execute(query, tuple(params))
        conn.commit()
    conn.close()


def delete_registration(player_puuid, guild_id):
    """
    Supprime l'inscription d'un joueur dans un serveur donné.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM registrations WHERE player_puuid = ? AND guild_id = ?", (player_puuid, guild_id))
    conn.commit()
    conn.close()


# ----- Opérations sur la table guilds -----

def insert_guild(guild_id, leaderboard_channel_id):
    """
    Insère un nouveau serveur (guild) avec son canal de leaderboard, si il n'existe pas.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guilds WHERE guild_id = ?", (guild_id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO guilds (guild_id, leaderboard_channel_id) VALUES (?, ?)",
            (guild_id, leaderboard_channel_id)
        )
        conn.commit()
    conn.close()


def get_guild(guild_id):
    """
    Récupère les informations d'un serveur (guild) à partir de son guild_id.
    Retourne un tuple ou None si non trouvé.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guilds WHERE guild_id = ?", (guild_id,))
    guild = cursor.fetchone()
    conn.close()
    return guild


def insert_match(match_id, player_puuid, guild_id, result, champion, kills, deaths, assists, damage, duration):
    """
    Insère un match dans la table matches si le match n'existe pas déjà.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM matches WHERE match_id = ?", (match_id,))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO matches 
            (match_id, player_puuid, guild_id, result, champion, kills, deaths, assists, damage, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (match_id, player_puuid, guild_id, result, champion, kills, deaths, assists, damage, duration))
        conn.commit()
    conn.close()


def get_matches(player_puuid, guild_id):
    """
    Récupère tous les matchs d'un joueur pour un serveur donné.
    Retourne une liste de tuples.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM matches WHERE player_puuid = ? AND guild_id = ?", (player_puuid, guild_id))
    matches = cursor.fetchall()
    conn.close()
    return matches


def get_all_registrations():
    """
    Récupère toutes les inscriptions en effectuant une jointure entre registrations et players.
    Retourne une liste de tuples :
    (player_puuid, guild_id, channel_id, last_match_id, tier, rank, lp, summoner_id, username)
    """
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT r.player_puuid, r.guild_id, r.channel_id, r.last_match_id, r.tier, r.rank, r.lp, p.summoner_id, p.username
        FROM registrations r
        JOIN players p ON r.player_puuid = p.puuid
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows
