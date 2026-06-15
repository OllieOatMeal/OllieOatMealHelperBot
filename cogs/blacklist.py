"""
cogs/blacklist.py
──────────────────
Per-system user blacklisting, persisted to data/blacklist_<system>.json.

Supported systems: music, tickets, applications

Commands (Staff+ required):
  /blacklist add    — Blacklist a user from a system
  /blacklist remove — Remove a user from a blacklist
  /blacklist check  — Check if a user is blacklisted
  /blacklist list   — List all blacklisted users for a system

Helper functions used by other cogs:
  is_blacklisted(user_id, system)     — Returns True/False
  get_blacklist_entry(user_id, system) — Returns the entry dict or None
"""

import json
import os
from datetime import datetime, timezone
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from config import has_any_role, CMD, PERMS


DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

SYSTEMS = ("music", "tickets", "applications")

def _path(system: str) -> str:
    return os.path.join(DATA_DIR, f"blacklist_{system}.json")

def _load(system: str) -> dict:
    """Load blacklist for a system. Returns {str(user_id): {reason, by, at}}"""
    try:
        with open(_path(system), "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save(system: str, data: dict):
    with open(_path(system), "w") as f:
        json.dump(data, f, indent=2)

async def is_blacklisted(user_id: int, system: str) -> bool:
    """Return True if the user is blacklisted from the given system."""
    data = _load(system)
    return str(user_id) in data

async def get_blacklist_entry(user_id: int, system: str) -> dict | None:
    """Return the blacklist entry for a user, or None."""
    data = _load(system)
    return data.get(str(user_id))

class Blacklist(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    blacklist_group = app_commands.Group(
        name=CMD["blacklist"],
        description="Manage user blacklists for music, tickets, and applications",
    )

    @blacklist_group.command(name=CMD["blacklist_add"], description="Blacklist a user from a system")
    @app_commands.describe(
        user="The user to blacklist",
        system="Which system to blacklist them from",
        reason="Reason for the blacklist",
    )
    @has_any_role(*PERMS["blacklist"])
    async def blacklist_add(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        system: Literal["music", "tickets", "applications"],
        reason: str = "No reason provided",
    ):
        data = _load(system)
        uid  = str(user.id)

        if uid in data:
            await interaction.response.send_message(
                f"⚠️ {user.mention} is already blacklisted from **{system}**.", ephemeral=True
            )
            return

        data[uid] = {
            "reason": reason,
            "by":     str(interaction.user),
            "by_id":  interaction.user.id,
            "at":     datetime.now(timezone.utc).isoformat(),
        }
        _save(system, data)

        embed = discord.Embed(
            title="🚫 User Blacklisted",
            colour=0xE74C3C,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="User",   value=f"{user.mention} (`{user}`)", inline=True)
        embed.add_field(name="System", value=system.capitalize(),           inline=True)
        embed.add_field(name="By",     value=interaction.user.mention,      inline=True)
        embed.add_field(name="Reason", value=reason,                        inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)

        await interaction.response.send_message(embed=embed)

        # DM the user
        try:
            dm_embed = discord.Embed(
                title=f"🚫 You have been blacklisted from {system.capitalize()}",
                description=f"**Server:** {interaction.guild.name}\n**Reason:** {reason}",
                colour=0xE74C3C,
                timestamp=datetime.now(timezone.utc),
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

    @blacklist_group.command(name=CMD["blacklist_remove"], description="Remove a user from a blacklist")
    @app_commands.describe(
        user="The user to unblacklist",
        system="Which system to remove them from",
    )
    @has_any_role(*PERMS["blacklist"])
    async def blacklist_remove(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        system: Literal["music", "tickets", "applications"],
    ):
        data = _load(system)
        uid  = str(user.id)

        if uid not in data:
            await interaction.response.send_message(
                f"⚠️ {user.mention} is not blacklisted from **{system}**.", ephemeral=True
            )
            return

        del data[uid]
        _save(system, data)

        embed = discord.Embed(
            title="✅ Blacklist Removed",
            colour=0x2ECC71,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="User",   value=f"{user.mention} (`{user}`)", inline=True)
        embed.add_field(name="System", value=system.capitalize(),           inline=True)
        embed.add_field(name="By",     value=interaction.user.mention,      inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)

        await interaction.response.send_message(embed=embed)

        # DM the user
        try:
            dm_embed = discord.Embed(
                title=f"✅ Your blacklist from {system.capitalize()} has been lifted",
                description=f"**Server:** {interaction.guild.name}",
                colour=0x2ECC71,
                timestamp=datetime.now(timezone.utc),
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            pass

    @blacklist_group.command(name=CMD["blacklist_check"], description="Check all blacklists for a user")
    @app_commands.describe(user="The user to check")
    @has_any_role(*PERMS["blacklist"])
    async def blacklist_check(self, interaction: discord.Interaction, user: discord.Member):
        embed = discord.Embed(
            title=f"🔍 Blacklist Check — {user}",
            colour=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        any_found = False
        for system in SYSTEMS:
            data  = _load(system)
            entry = data.get(str(user.id))
            if entry:
                any_found = True
                at = entry.get("at", "Unknown")[:10]
                embed.add_field(
                    name=f"🚫 {system.capitalize()}",
                    value=f"**Reason:** {entry.get('reason', 'N/A')}\n**By:** {entry.get('by', 'N/A')}\n**Date:** {at}",
                    inline=False,
                )

        if not any_found:
            embed.description = f"{user.mention} is not blacklisted from any system."
            embed.colour = 0x2ECC71

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @blacklist_group.command(name=CMD["blacklist_list"], description="List all blacklisted users for a system")
    @app_commands.describe(system="Which system to list blacklisted users for")
    @has_any_role(*PERMS["blacklist"])
    async def blacklist_list(
        self,
        interaction: discord.Interaction,
        system: Literal["music", "tickets", "applications"],
    ):
        data = _load(system)

        if not data:
            await interaction.response.send_message(
                f"No users are blacklisted from **{system}**.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🚫 {system.capitalize()} Blacklist — {len(data)} user{'s' if len(data) != 1 else ''}",
            colour=0xE74C3C,
            timestamp=datetime.now(timezone.utc),
        )

        lines = []
        for uid, entry in list(data.items())[:25]:
            at     = entry.get("at", "")[:10]
            reason = entry.get("reason", "N/A")
            lines.append(f"<@{uid}> — {reason} *(added {at} by {entry.get('by', '?')})*")

        if len(data) > 25:
            lines.append(f"*…and {len(data) - 25} more*")

        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have permission to manage blacklists.", ephemeral=True)
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Blacklist(bot))
    print("Blacklist cog loaded")