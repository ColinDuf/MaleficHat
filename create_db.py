import logging
import sqlite3


def create_db():
    # Connexion (ou création) de la base de données
    logging.info(f" Starting DB creation...")
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Création de la table des joueurs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        summoner_id TEXT NOT NULL,
        puuid TEXT PRIMARY KEY,
        username TEXT NOT NULL
    );
    """)

    # Création de la table d'inscription (registrations) qui fait le lien entre joueurs et guilds
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS registrations (
        player_puuid TEXT,
        guild_id TEXT,
        channel_id TEXT,
        last_match_id TEXT,
        alerte BOOLEAN DEFAULT 0,
        tier TEXT,
        rank TEXT,
        lp INTEGER,
        lp_24h INTEGER DEFAULT 0,
        lp_7d INTEGER DEFAULT 0,
        PRIMARY KEY (player_puuid, guild_id),
        FOREIGN KEY (player_puuid) REFERENCES players(puuid)
    );
    """)

    # Création de la table des guilds (serveurs Discord)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS guilds (
        guild_id TEXT PRIMARY KEY,
        leaderboard_channel_id TEXT
    );
    """)

    # Optionnel : Création de la table des matchs pour enregistrer l'historique des parties
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS matches (
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
        FOREIGN KEY (player_puuid) REFERENCES players(puuid)
    );
    """)

    # Enregistrement des modifications et fermeture de la connexion
    conn.commit()
    conn.close()
    logging.info(f"Database created!")

