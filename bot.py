# ══════════════════════════════════════════════════════════════════════════════
# bot.py — Entry point
# ══════════════════════════════════════════════════════════════════════════════

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("─" * 40)

    try:
        guild = discord.Object(id=1117187705319723133)

        synced = await bot.tree.sync(guild=guild)

        print(f"\n⚡ Synced {len(synced)} slash command(s)")

        print("\nRegistered commands:")
        for cmd in bot.tree.get_commands(guild=guild):
            print(f" - {cmd.name}")

    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="OllieOatMeal's Den"
        )
    )


async def load_cogs():
    cogs = [
        "cogs.logging",
        "cogs.moderation",
        "cogs.reaction_roles",
        "cogs.embeds",
        "cogs.tickets",
        "cogs.applications",
        "cogs.music",
    ]

    print("Loading cogs...")

    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"✔ Loaded {cog}")
        except Exception as e:
            print(f"✘ Failed to load {cog}: {e}")


async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
