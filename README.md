# MaleficHat

A Discord bot that queries the Riot Games API and tracks player statistics.

## Requirements

- Python 3.10 or newer

## Installation

Create and activate a virtual environment, then install the dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

The bot expects the following environment variables to be set:

- `DISCORD_TOKEN` &ndash; your Discord bot token.
- `RIOT_API_KEY` &ndash; your Riot Games API key.

They can be exported in your shell or placed in a `.env` file.

## Running the Bot

1. Create the local database (only once):
   ```bash
   python create_db.py
   ```
2. Start the bot:
   ```bash
   python bot.py
   ```

For the music reaction feature to work, place your MP3 files in the
`music/` directory and install `ffmpeg` on your system. Reacting to either
the victory/defeat or in‑game status embeds with a supported emoji will play
a sound. The bot fetches member information as needed, so no privileged
intents are required.

When the bot loses permission to send alerts in a configured channel, it
automatically disables alerts for that player in that server to avoid cluttering
the logs.

## Running Tests

With the virtual environment active and dependencies installed, run:

```bash
pytest
```
