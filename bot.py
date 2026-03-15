import json
import os
import aiohttp
import discord
from discord.ext import commands, tasks
from discord import app_commands
from config import TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, DISCORD_TOKEN

SNAPSHOT_FILE = "twitch_badges_snapshot.json"
CHANNELS_FILE = "subscribed_channels.json"

async def get_twitch_token(session):
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    async with session.post(url, params=params) as response:
        data = await response.json()
        return data["access_token"]

async def fetch_badges(session, token):
    url = "https://api.twitch.tv/helix/chat/badges/global"
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {token}"
    }
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            return await response.json()
        print(f"Failed to fetch badges: {response.status}")
        return None

def load_snapshot():
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE, "r") as f:
            return json.load(f)
    return {}

def save_snapshot(data):
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_subscribed_channels():
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_subscribed_channels(channels):
    with open(CHANNELS_FILE, "w") as f:
        json.dump(list(channels), f)

def find_new_badges(old_data, new_data):
    old_ids = set()
    for badge in old_data.get("data", []):
        for version in badge.get("versions", []):
            old_ids.add(f"{badge['set_id']}:{version['id']}")

    new_badges = []
    for badge in new_data.get("data", []):
        for version in badge.get("versions", []):
            badge_key = f"{badge['set_id']}:{version['id']}"
            if badge_key not in old_ids:
                new_badges.append({
                    "set_id": badge["set_id"],
                    "version_id": version["id"],
                    "title": version.get("title", "Unknown"),
                    "image": version.get("image_url_4x", "")
                })

    return new_badges

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
subscribed_channels = load_subscribed_channels()

@bot.command(name="status")
async def status(ctx):
    await ctx.send("Bot is running and watching for badge updates.")

@bot.command(name="checkbadges")
async def check_badges_command(ctx):
    async with aiohttp.ClientSession() as session:
        token = await get_twitch_token(session)
        new_data = await fetch_badges(session, token)

    if new_data is None:
        await ctx.send("Failed to fetch badge data. Try again later.")
        return

    old_data = load_snapshot()

    if not old_data:
        save_snapshot(new_data)
        badge_count = sum(len(b.get("versions", [])) for b in new_data.get("data", []))
        await ctx.send(f"First run: saved {badge_count} existing badges as baseline. Future checks will only show new badges.")
        return

    new_badges = find_new_badges(old_data, new_data)

    if new_badges:
        for badge in new_badges:
            streamdb_url = f"https://www.streamdatabase.com/twitch/global-badges/{badge['set_id']}/{badge['version_id']}"
            embed = discord.Embed(
                title=f"New Badge: {badge['title']}",
                description=f"Set: {badge['set_id']} | Version: {badge['version_id']}",
                url=streamdb_url,
                color=discord.Color.purple()
            )
            if badge["image"]:
                embed.set_thumbnail(url=badge["image"])
            await ctx.send(embed=embed)
        save_snapshot(new_data)
    else:
        await ctx.send("No new badges found.")

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="TBT BadgeBot Commands",
        color=discord.Color.blurple()
    )
    embed.add_field(name="!status", value="Check if the bot is running", inline=False)
    embed.add_field(name="!checkbadges", value="Manually check for new Twitch badges", inline=False)
    embed.add_field(name="/subscribe", value="Subscribe this channel to hourly badge updates", inline=False)
    embed.add_field(name="/unsubscribe", value="Unsubscribe this channel from updates", inline=False)
    await ctx.send(embed=embed)

@bot.tree.command(name="subscribe", description="Subscribe this channel to badge update notifications")
async def subscribe(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("This command only works in text channels.", ephemeral=True)
        return
    subscribed_channels.add(interaction.channel.id)
    save_subscribed_channels(subscribed_channels)
    await interaction.response.send_message(
        "This channel will now receive badge update notifications.", ephemeral=True
    )

@bot.tree.command(name="unsubscribe", description="Unsubscribe this channel from badge update notifications")
async def unsubscribe(interaction: discord.Interaction):
    if interaction.channel.id in subscribed_channels:
        subscribed_channels.discard(interaction.channel.id)
        save_subscribed_channels(subscribed_channels)
        await interaction.response.send_message("This channel has been unsubscribed.", ephemeral=True)
    else:
        await interaction.response.send_message("This channel is not subscribed.", ephemeral=True)

@tasks.loop(hours=1)
async def scheduled_badge_check():
    if not subscribed_channels:
        return

    async with aiohttp.ClientSession() as session:
        token = await get_twitch_token(session)
        new_data = await fetch_badges(session, token)

    if new_data is None:
        print("Scheduled check failed: could not fetch badges.")
        return

    old_data = load_snapshot()

    if not old_data:
        save_snapshot(new_data)
        return

    new_badges = find_new_badges(old_data, new_data)

    if not new_badges:
        return

    for badge in new_badges:
        streamdb_url = f"https://www.streamdatabase.com/twitch/global-badges/{badge['set_id']}/{badge['version_id']}"
        embed = discord.Embed(
            title=f"New Twitch Badge: {badge['title']}",
            description=f"**{badge['set_id']}** — version {badge['version_id']}",
            url=streamdb_url,
            color=discord.Color.purple()
        )
        if badge["image"]:
            embed.set_image(url=badge["image"])
        embed.set_footer(text="View full badge details on StreamDatabase")

        for channel_id in subscribed_channels:
            channel = bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    print(f"No access to channel {channel_id}")

    save_snapshot(new_data)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")
    scheduled_badge_check.start()

bot.run(DISCORD_TOKEN)
