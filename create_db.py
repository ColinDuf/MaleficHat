import logging
import sqlite3

DB_PATH = "database.db"

def create_db():
    logging.info("Starting DB creation...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON;")

    c.execute("""
        CREATE TABLE IF NOT EXISTS guild (
            guild_id INTEGER PRIMARY KEY,
            leaderboard_channel_id INTEGER
        );
        """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS player (
            username TEXT NOT NULL,
            puuid TEXT PRIMARY KEY,
            summoner_id TEXT NOT NULL,
            rank TEXT,
            tier TEXT,
            lp INTEGER,
            lp_24h INTEGER,
            lp_7d INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS player_guild (
            player_puuid TEXT    NOT NULL,
            guild_id      INTEGER NOT NULL,
            channel_id    INTEGER NOT NULL,
            last_match_id TEXT,
            PRIMARY KEY (player_puuid, guild_id),
            FOREIGN KEY (player_puuid) REFERENCES player(puuid),
            FOREIGN KEY (guild_id)     REFERENCES guild(guild_id)
            );
        """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
        leaderboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id       INTEGER NOT NULL,
        FOREIGN KEY (guild_id) REFERENCES guild(guild_id)
            );
        """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard_player (
            leaderboard_id INTEGER NOT NULL,
            player_puuid   TEXT    NOT NULL,
            PRIMARY KEY (leaderboard_id, player_puuid),
            FOREIGN KEY (leaderboard_id) REFERENCES leaderboard(leaderboard_id),
            FOREIGN KEY (player_puuid)   REFERENCES player(puuid)
            );
        """)

    conn.commit()
    conn.close()
    logging.info("Database created!")
