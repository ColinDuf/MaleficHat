import sqlite3
from discord import app_commands, Interaction

DB_PATH = "/root/MaleficHat/Backend/database.db"

def get_connection():
    """Retourne une connexion SQLite avec les FK activées."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def insert_player(puuid: str,
                  username: str,
                  tier: str,
                  rank: str,
                  lp: int,
                  region: str,
                  flex_tier: str = None,
                  flex_rank: str = None,
                  flex_lp: int = None):
    """
    Insert or update des données globales du joueur.
    """
    conn = get_connection()
    c = conn.cursor()
    # Insert initial si absent
    c.execute(
        """
        INSERT OR IGNORE INTO player
          (puuid, username, tier, rank, lp, region, flex_tier, flex_rank, flex_lp, lp_24h, lp_7d, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (puuid, username, tier, rank, lp, region, flex_tier, flex_rank, flex_lp),
    )
    c.execute(
        """
        UPDATE player
        SET username = ?,
            tier = ?,
            rank = ?,
            lp = ?,
            region = ?,
            flex_tier = ?,
            flex_rank = ?,
            flex_lp = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE puuid = ?
        """,
        (username, tier, rank, lp, region, flex_tier, flex_rank, flex_lp, puuid),
    )
    conn.commit()
    conn.close()

def update_player_global(puuid: str,
                         tier: str = None,
                         rank: str = None,
                         lp: int = None,
                         lp_change: int = None,
                         username: str = None,
                         region: str = None,
                         flex_tier: str = None,
                         flex_rank: str = None,
                         flex_lp: int = None):
    """
    Met à jour les champs de la table player pour un joueur donné.

    - Si lp_change != None : on **cumule** lp_change à lp_24h et lp_7d.
    - Sinon, lp_24h et lp_7d ne sont pas modifiés (on ne les écrase pas).
    - Les autres champs (tier, rank, lp, username) sont mis à jour uniquement s'ils sont non-None.
    """
    updates = []
    params = []

    if username is not None:
        updates.append("username = ?")
        params.append(username)
    if tier is not None:
        updates.append("tier = ?")
        params.append(tier)
    if rank is not None:
        updates.append("rank = ?")
        params.append(rank)
    if lp is not None:
        updates.append("lp = ?")
        params.append(lp)
    if region is not None:
        updates.append("region = ?")
        params.append(region)
    if flex_tier is not None:
        updates.append("flex_tier = ?")
        params.append(flex_tier)
    if flex_rank is not None:
        updates.append("flex_rank = ?")
        params.append(flex_rank)
    if flex_lp is not None:
        updates.append("flex_lp = ?")
        params.append(flex_lp)

    # Cas de cumul : si lp_change fourni, on fait « lp_24h = lp_24h + lp_change » et même pour lp_7d
    if lp_change is not None:
        updates.append("lp_24h = COALESCE(lp_24h, 0) + ?")
        params.append(lp_change)
        updates.append("lp_7d  = COALESCE(lp_7d, 0)  + ?")
        params.append(lp_change)

    if not updates:
        # Rien à mettre à jour → on sort
        return

    # Ajout de l’horodatage de mise à jour
    updates.append("updated_at = CURRENT_TIMESTAMP")

    query = f"UPDATE player SET {', '.join(updates)} WHERE puuid = ?"
    params.append(puuid)

    conn = get_connection()
    c = conn.cursor()
    c.execute(query, tuple(params))
    conn.commit()
    conn.close()

# ----- Opérations sur la table player_guild (liaisons serveur) -----

def insert_player_guild(puuid: str,
                        guild_id: int,
                        channel_id: int,
                        last_match_id: str = None):
    """
    Associe un joueur à une guilde et au salon d'alerte, avec son dernier match.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO player_guild
          (player_puuid, guild_id, channel_id, last_match_id)
        VALUES (?, ?, ?, ?)
    """, (puuid, guild_id, channel_id, last_match_id))
    conn.commit()
    conn.close()

def update_player_guild(puuid: str,
                        guild_id: int,
                        channel_id: int = None,
                        last_match_id: str = None):
    """
    Met à jour les champs de la table player_guild pour une paire joueur↔guilde.
    Seuls channel_id et last_match_id non-None sont pris en compte.
    """
    updates = []
    params = []

    if channel_id is not None:
        updates.append("channel_id = ?")
        params.append(channel_id)
    if last_match_id is not None:
        updates.append("last_match_id = ?")
        params.append(last_match_id)

    if not updates:
        return

    query = f"UPDATE player_guild SET {', '.join(updates)} WHERE player_puuid = ? AND guild_id = ?"
    params.extend([puuid, guild_id])

    conn = get_connection()
    c = conn.cursor()
    c.execute(query, tuple(params))
    conn.commit()
    conn.close()

def delete_player(puuid: str, guild_id: int):
    """Supprime l'inscription d'un joueur dans une guilde."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM player_guild WHERE player_puuid = ? AND guild_id = ?", (puuid, guild_id))
    conn.commit()
    conn.close()

# ----- Requêtes de consultation -----

def get_player(puuid: str, guild_id: int):
    """Récupère un joueur pour une guilde via jointure."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT
            p.puuid, p.username,
            pg.guild_id, pg.channel_id, p.region, pg.last_match_id,
            p.tier, p.rank, p.lp, p.lp_24h, p.lp_7d,
            p.flex_tier, p.flex_rank, p.flex_lp
        FROM player p
            JOIN player_guild pg ON p.puuid = pg.player_puuid
        WHERE p.puuid = ? AND pg.guild_id = ?
        """,
        (puuid, guild_id),
    )
    row = c.fetchone()
    conn.close()
    return row

def get_all_players():
    """Liste tous les joueurs et leurs associations."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT
            p.puuid, p.username,
            pg.guild_id, pg.channel_id, p.region, pg.last_match_id,
            p.tier, p.rank, p.lp, p.lp_24h, p.lp_7d,
            p.flex_tier, p.flex_rank, p.flex_lp
        FROM player p
            JOIN player_guild pg ON p.puuid = pg.player_puuid
        """
    )
    rows = c.fetchall()
    conn.close()
    return rows

def get_player_by_username(username: str, guild_id: int = None):
    """Récupère un joueur par username, optionnellement filtré par guilde."""
    conn = get_connection()
    c = conn.cursor()
    if guild_id is not None:
        c.execute(
            """
            SELECT
                p.puuid, p.username,
                pg.guild_id, pg.channel_id, p.region, pg.last_match_id,
                p.tier, p.rank, p.lp, p.lp_24h, p.lp_7d,
                p.flex_tier, p.flex_rank, p.flex_lp
            FROM player p
                JOIN player_guild pg ON p.puuid = pg.player_puuid
            WHERE p.username = ? AND pg.guild_id = ?
            """,
            (username, guild_id),
        )
        result = c.fetchone()
    else:
        c.execute("SELECT puuid, username, region FROM player WHERE username = ?", (username,))
        result = c.fetchone()
    conn.close()
    return result

async def username_autocomplete(interaction: Interaction, current: str):
    """Autocomplétion des usernames pour une guilde donnée."""
    guild_id = interaction.guild.id
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
              SELECT p.username
              FROM player p
                       JOIN player_guild pg ON p.puuid = pg.player_puuid
              WHERE pg.guild_id = ?
              """, (guild_id,))
    rows = c.fetchall()
    conn.close()
    choices = [row[0] for row in rows]
    return [
        app_commands.Choice(name=choice, value=choice)
        for choice in choices if current.lower() in choice.lower()
    ]

# ----- Opérations sur la table guild -----

def insert_guild(guild_id: int,
                 leaderboard_channel_id: int | None,
                 flex_enabled: int | None = 0):
    """Insert or update guild configuration.

    Uses ``INSERT OR IGNORE`` followed by an ``UPDATE`` so that existing
    rows aren't replaced, which previously could violate foreign key
    constraints for related tables.
    """
    conn = get_connection()
    c = conn.cursor()

    # Ensure a row exists for this guild
    c.execute(
        """
        INSERT OR IGNORE INTO guild (guild_id, leaderboard_channel_id, flex_enabled)
        VALUES (?, ?, COALESCE(?, 0))
        """,
        (guild_id, leaderboard_channel_id, flex_enabled),
    )

    # Update provided fields without clobbering existing data
    updates = []
    params: list[object] = []
    if leaderboard_channel_id is not None:
        updates.append("leaderboard_channel_id = ?")
        params.append(leaderboard_channel_id)
    if flex_enabled is not None:
        updates.append("flex_enabled = ?")
        params.append(flex_enabled)
    if updates:
        params.append(guild_id)
        c.execute(
            f"UPDATE guild SET {', '.join(updates)} WHERE guild_id = ?",
            params,
        )

    conn.commit()
    conn.close()

def set_guild_flex_mode(guild_id: int, enabled: bool) -> None:
    """Toggle flex mode for a guild."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE guild SET flex_enabled = ? WHERE guild_id = ?",
        (1 if enabled else 0, guild_id)
    )
    conn.commit()
    conn.close()

def get_guild(guild_id: int):
    """Retrieve guild info if present."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT guild_id, leaderboard_channel_id, flex_enabled FROM guild WHERE guild_id = ?",
        (guild_id,)
    )
    result = c.fetchone()
    conn.close()
    return result

# ----- Opérations sur la table leaderboard -----

def get_leaderboard_by_guild(guild_id: int):
    """Renvoie le leaderboard_id pour une guilde si créé, sinon None."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT leaderboard_id FROM leaderboard WHERE guild_id = ?", (guild_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def insert_leaderboard(guild_id: int) -> int:
    """Crée un nouveau leaderboard pour la guilde et renvoie son ID."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO leaderboard (guild_id) VALUES (?)", (guild_id,))
    lb_id = c.lastrowid
    conn.commit()
    conn.close()
    return lb_id

def delete_leaderboard(guild_id: int):
    """Supprime le leaderboard d'une guilde et réinitialise son channel."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT leaderboard_id FROM leaderboard WHERE guild_id = ?",
        (guild_id,)
    )
    row = c.fetchone()
    if row:
        c.execute(
            "DELETE FROM leaderboard_player WHERE leaderboard_id = ?",
            (row[0],),
        )
    c.execute("DELETE FROM leaderboard WHERE guild_id = ?", (guild_id,))
    c.execute(
        "UPDATE guild SET leaderboard_channel_id = NULL WHERE guild_id = ?",
        (guild_id,)
    )
    conn.commit()
    conn.close()

def insert_leaderboard_member(leaderboard_id: int, player_puuid: str):
    """Ajoute un joueur au leaderboard."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO leaderboard_player (leaderboard_id, player_puuid) VALUES (?, ?)",
        (leaderboard_id, player_puuid)
    )
    conn.commit()
    conn.close()

def delete_leaderboard_member(leaderboard_id: int, player_puuid: str):
    """Retire un joueur du leaderboard."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "DELETE FROM leaderboard_player WHERE leaderboard_id = ? AND player_puuid = ?",
        (leaderboard_id, player_puuid)
    )
    conn.commit()
    conn.close()

def get_leaderboard_data(leaderboard_id: int, guild_id: int):
    """
    Récupère les données à afficher pour le leaderboard :
    username, tier, rank, current LP, LP 24h, LP 7j
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT
            p.username,
            p.tier,
            p.rank,
            p.lp,
            p.lp_24h,
            p.lp_7d
        FROM leaderboard    AS lb
                 JOIN leaderboard_player AS lp_player
                      ON lb.leaderboard_id = lp_player.leaderboard_id
                 JOIN player        AS p
                      ON lp_player.player_puuid = p.puuid
        WHERE lb.guild_id       = ?
          AND lb.leaderboard_id = ?
        """,
        (guild_id, leaderboard_id),
    )
    rows = c.fetchall()
    conn.close()
    return rows


# ----- Remise à zéro des LP -----

def reset_all_lp_24h():
    """Remet à zéro lp_24h pour tous les joueurs."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE player SET lp_24h = 0")
    conn.commit()
    conn.close()

def reset_all_lp_7d():
    """Remet à zéro lp_7d pour tous les joueurs."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE player SET lp_7d = 0")
    conn.commit()
    conn.close()

# ----- Helpers -----

def count_players() -> int:
    """Return the total number of registered players."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM player")
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0
