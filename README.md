# TBT BadgeBot — Twitch Badge Tracker

A Discord bot that monitors Twitch for new global badges and notifies subscribed channels automatically.

## What it does

- Polls the Twitch Helix API every hour for new global badge releases
- Sends rich embed notifications with badge images to subscribed Discord channels
- Handles first-run setup silently — saves the current badge state as a baseline without flooding the channel
- Persists subscriptions and badge state across restarts

## Commands

| Command | Description |
|---------|-------------|
| `!checkbadges` | Manually check for new Twitch badges |
| `!status` | Check if the bot is running |
| `!help` | List available commands |
| `/subscribe` | Subscribe the current channel to automatic badge notifications |
| `/unsubscribe` | Unsubscribe the current channel |

## Setup

### Prerequisites

- Python 3.10+
- A [Twitch Developer Application](https://dev.twitch.tv/console/apps) (Client ID and Client Secret)
- A [Discord Bot Application](https://discord.com/developers/applications) with Message Content Intent enabled

### Installation

```bash
git clone https://github.com/gl1z/twitch-badge-tracker.git
cd twitch-badge-tracker
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_client_secret
DISCORD_TOKEN=your_discord_bot_token
```

### Run

```bash
python bot.py
```

## How it works

The bot authenticates with Twitch using OAuth client credentials, then fetches the full list of global badges from the Helix API. It compares each `set_id:version_id` pair against a local snapshot. Any pairs not in the previous snapshot are new badges — the bot sends a Discord embed for each one and updates the snapshot.

On first run, the bot saves all current badges as a baseline without sending notifications.

## Tech Stack

- **discord.py** - Discord bot framework
- **aiohttp** - Async HTTP client for Twitch API requests
- **python-dotenv** - Environment variable management
- **Twitch Helix API** - Badge data source

## License

MIT
