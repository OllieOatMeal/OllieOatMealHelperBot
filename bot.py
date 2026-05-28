# ══════════════════════════════════════════════════════════════════════════════
# bot.py — Entry point
# ══════════════════════════════════════════════════════════════════════════════

import discord
from discord.ext import commands

TOKEN = "MTUwNzQ1NjI3NjE2MTEwMjAzNg.GoyIcS.MPoAbPqPqjVhpUK673jmP80625ZBvD-Tr74xVA"  # ← Paste your bot token here

# ── Intents ───────────────────────────────────────────────────────────────────
intents = discord.Intents.all()

# ── Bot ───────────────────────────────────────────────────────────────────────
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("─" * 40)

    cogs = ["cogs.logging", "cogs.moderation", "cogs.reaction_roles", "cogs.embeds"]
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"  ✔ Loaded {cog}")
        except Exception as e:
            print(f"  ✘ Failed to load {cog}: {e}")

    try:
        synced = await bot.tree.sync()
        print(f"\n⚡ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, name="the server"
        )
    )


if __name__ == "__main__":
    bot.run(TOKEN)