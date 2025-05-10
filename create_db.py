import logging
import sqlite3

def create_db():
    logging.info("Starting DB creation...")
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Table player : contient les informations du joueur ainsi que ses données d'inscription
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS player (
        summoner_id TEXT NOT NULL,
        puuid TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        guild_id TEXT,             -- Le guild dans lequel le joueur est enregistré
        channel_id TEXT,           -- Le channel où il a été enregistré
        last_match_id TEXT,        -- Le dernier match enregistré
        tier TEXT,
        rank TEXT,
        lp INTEGER,
        lp_24h INTEGER DEFAULT 0,
        lp_7d INTEGER DEFAULT 0
    );
    """)

    # Table guild : pour stocker le channel du leaderboard par guild
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS guild (
        guild_id TEXT PRIMARY KEY,
        leaderboard_channel_id TEXT
    );
    """)

    # Table match : pour enregistrer l'historique des parties (match au singulier)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS match (
        match_id TEXT PRIMARY KEY,
        player_puuid TEXT,
        guild_id TEXT,
        result TEXT,
        champion TEXT,
        kills INTEGER,
        deaths INTEGER,
        assists INTEGER,
        damage INTEGER,
        duration TEXT,
        match_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (player_puuid) REFERENCES player(puuid)
    );
    """)

    # Table leaderboard (reste inchangée, elle est déjà au singulier)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leaderboard (
        guild_id TEXT,
        leaderboard_id TEXT,
        player_puuid TEXT,
        PRIMARY KEY (guild_id, leaderboard_id, player_puuid),
        FOREIGN KEY (player_puuid) REFERENCES player(puuid)
    );
    """)

    conn.commit()
    conn.close()
    logging.info("Database created!")
