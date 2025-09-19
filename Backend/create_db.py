import logging
import sqlite3

DB_PATH = "Backend/database.db"

def ensure_columns(cursor, table_name: str, columns) -> None:
    """Add missing columns to an existing table without dropping data."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = {row[1] for row in cursor.fetchall()}

    for column_name, column_definition in columns.items():
        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )

def create_db():
    logging.info("Starting DB creation...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON;")

    c.execute("""
        CREATE TABLE IF NOT EXISTS guild (
            guild_id INTEGER PRIMARY KEY,
            leaderboard_channel_id INTEGER,
            flex_enabled INTEGER DEFAULT 0,
            daily_recap_enabled INTEGER DEFAULT 0,
            weekly_recap_enabled INTEGER DEFAULT 0
        );
        """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS player (
            username TEXT NOT NULL,
            puuid TEXT PRIMARY KEY,
            rank TEXT,
            tier TEXT,
            lp INTEGER,
            region TEXT,
            flex_rank TEXT,
            flex_tier TEXT,
            flex_lp INTEGER,
            lp_24h INTEGER,
            lp_7d INTEGER,
            current_game_status TEXT DEFAULT 'offline',
            current_game_updated_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

    ensure_columns(
        c,
        "player",
        {
            "current_game_status": "TEXT DEFAULT 'offline'",
            "current_game_updated_at": "DATETIME"
        },
    )

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
