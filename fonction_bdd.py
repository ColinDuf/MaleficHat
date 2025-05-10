import sqlite3

import discord
from discord import app_commands

DB_PATH = "database.db"

def get_connection():
    """Retourne une connexion à la base de données SQLite."""
    return sqlite3.connect(DB_PATH)

# ----- Opérations sur la table player -----

def insert_player(summoner_id, puuid, username, guild_id, channel_id, last_match_id, tier, rank, lp, lp_24h=0, lp_7d=0):
    """
    Insère un joueur dans la table player s'il n'existe pas déjà.
    On stocke ici aussi les informations d'inscription.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM player WHERE puuid = ?", (puuid,))
    if not cursor.fetchone():
        cursor.execute(
            """INSERT INTO player 
            (summoner_id, puuid, username, guild_id, channel_id, last_match_id, tier, rank, lp, lp_24h, lp_7d)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (summoner_id, puuid, username, guild_id, channel_id, last_match_id, tier, rank, lp, lp_24h, lp_7d)
        )
        conn.commit()
    conn.close()

def update_player(puuid, guild_id, channel_id=None, last_match_id=None,
                  tier=None, rank=None, lp=None, lp_24h=None, lp_7d=None):
    """
    Met à jour les informations d'un joueur dans la table player.
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
        params.extend([puuid])
        query = "UPDATE player SET " + ", ".join(updates) + " WHERE puuid = ?"
        cursor.execute(query, tuple(params))
        conn.commit()
    conn.close()

def delete_player(puuid, guild_id):
    """
    Supprime un joueur de la table player pour un guild donné.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM player WHERE puuid = ? AND guild_id = ?", (puuid, guild_id))
    conn.commit()
    conn.close()


def get_player(puuid, guild_id):
    """
    Récupère les informations d'un joueur à partir de son puuid et du guild_id.
    Retourne un tuple (summoner_id, puuid, username, guild_id, channel_id, last_match_id, tier, rank, lp, lp_24h, lp_7d)
    ou None si non trouvé.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM player WHERE puuid = ? AND guild_id = ?", (puuid, guild_id))
    player = cursor.fetchone()
    conn.close()
    return player


def get_player_by_username(username):
    """
    Récupère les informations d'un joueur à partir de son username.
    Retourne un tuple (summoner_id, puuid, username, guild_id, channel_id, last_match_id, tier, rank, lp, lp_24h, lp_7d)
    ou None si non trouvé.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM player WHERE username = ?", (username,))
    player = cursor.fetchone()
    conn.close()
    return player

def get_all_players():
    """
    Récupère tous les joueurs enregistrés.
    Retourne une liste de tuples.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT summoner_id, puuid, username, guild_id, channel_id, last_match_id, tier, rank, lp, lp_24h, lp_7d
        FROM player
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

async def username_autocomplete(interaction: discord.Interaction, current: str):
    guild_id = str(interaction.guild.id)
    conn = get_connection()
    cursor = conn.cursor()
    # Ici, on suppose que le joueur est enregistré dans un seul guild (sinon il faudra ajuster)
    cursor.execute("""
        SELECT username
        FROM player
        WHERE guild_id = ?
    """, (guild_id,))
    rows = cursor.fetchall()
    conn.close()
    usernames = [row[0] for row in rows]
    return [
        app_commands.Choice(name=username, value=username)
        for username in usernames if current.lower() in username.lower()
    ]

# ----- Opérations sur la table guild -----

def insert_guild(guild_id, leaderboard_channel_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guild WHERE guild_id = ?", (guild_id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO guild (guild_id, leaderboard_channel_id) VALUES (?, ?)",
            (guild_id, leaderboard_channel_id)
        )
        conn.commit()
    conn.close()

def get_guild(guild_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM guild WHERE guild_id = ?", (guild_id,))
    guild = cursor.fetchone()
    conn.close()
    return guild

# ----- Opérations sur la table match -----

def insert_match(match_id, player_puuid, guild_id, result, champion, kills, deaths, assists, damage, duration):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM match WHERE match_id = ?", (match_id,))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO match 
            (match_id, player_puuid, guild_id, result, champion, kills, deaths, assists, damage, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (match_id, player_puuid, guild_id, result, champion, kills, deaths, assists, damage, duration))
        conn.commit()
    conn.close()

def get_matches(player_puuid, guild_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM match WHERE player_puuid = ? AND guild_id = ?", (player_puuid, guild_id))
    matches = cursor.fetchall()
    conn.close()
    return matches

# ----- Opérations sur la table leaderboard -----

def insert_leaderboard_member(guild_id, leaderboard_id, player_puuid):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO leaderboard (guild_id, leaderboard_id, player_puuid)
        VALUES (?, ?, ?)
    """, (guild_id, leaderboard_id, player_puuid))
    conn.commit()
    conn.close()

def delete_leaderboard_member(guild_id, leaderboard_id, player_puuid):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM leaderboard
        WHERE guild_id = ? AND leaderboard_id = ? AND player_puuid = ?
    """, (guild_id, leaderboard_id, player_puuid))
    conn.commit()
    conn.close()

def get_leaderboard_data(leaderboard_id, guild_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.username, pl.tier, pl.rank, pl.lp_24h, pl.lp_7d
        FROM leaderboard lm
        JOIN player p ON lm.player_puuid = p.puuid
        JOIN player pl ON lm.player_puuid = pl.puuid
        WHERE lm.guild_id = ? AND lm.leaderboard_id = ?
    """, (guild_id, leaderboard_id))
    rows = cursor.fetchall()
    conn.close()
    return rows
