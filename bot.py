import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env file (DISCORD_TOKEN, etc.)
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# Enable all default intents plus message content (needed to read message text)
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
)


@bot.event
async def on_ready():
    """Fires once the bot has connected and is ready to receive events."""
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("─" * 40)

    # Sync slash commands with Discord so they appear in the UI
    try:
        synced = await bot.tree.sync()
        print(f"\n⚡ Synced {len(synced)} slash command(s)")
        print("\nRegistered commands:")
        for cmd in bot.tree.get_commands():
            print(f"  - /{cmd.name}")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

    # Set the bot's presence/status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="The Server...",
        )
    )


async def load_cogs():
    """Load every feature module (cog) from the cogs/ directory."""
    cogs = [
        "cogs.logging",       # Server event logging
        "cogs.moderation",    # Ban, kick, mute, warn, etc.
        "cogs.reaction_roles",# Self-assignable roles via reactions
        "cogs.embeds",        # Embed builder & announcement tools
        "cogs.tickets",       # Support ticket system
        "cogs.applications",  # Member / staff application system
        "cogs.music",         # Music playback commands
        "cogs.blacklist",     # Per-system user blacklisting
        "cogs.utility",       # General utility commands (.support, staff ranks)
        "cogs.modmail",       # Modmail system
    ]

    print("Loading cogs...")
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"  ✔ Loaded {cog}")
        except Exception as e:
            print(f"  ✘ Failed to load {cog}: {e}")


async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
