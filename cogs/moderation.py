"""
cogs/moderation.py
───────────────────
Slash commands for moderating server members.
All actions are logged to #mod-logs via send_mod_log().

Commands (and required minimum role):
  /ban        — Admin+
  /unban      — Head Admin+
  /kick       — Staff+
  /mute       — Staff+
  /unmute     — Admin+
  /warn       — Staff+
  /warnings   — Staff+
  /clearwarns — Head Admin+
  /purge      — Admin+
  /lock       — Head Admin+
  /unlock     — Head Admin+
  /slowmode   — Head Admin+
  /nick       — Staff+
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import re

from config import (
    has_any_role, CMD, PERMS,
    MOD_LOG_CHANNEL_ID, MOD_LOG_CHANNEL_NAME,
)

# In-memory warning store: {guild_id: {user_id: [reason, ...]}}
# Note: warnings are lost if the bot restarts. For persistence, consider saving to a JSON file.
warnings: dict[int, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))


def parse_duration(duration: str) -> timedelta | None:
    """
    Parse a short-hand duration string into a timedelta.
    Accepted formats: 10s, 5m, 2h, 1d
    Returns None if the string doesn't match.
    """
    match = re.fullmatch(r"(\d+)([smhd])", duration.strip().lower())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    return {
        "s": timedelta(seconds=value),
        "m": timedelta(minutes=value),
        "h": timedelta(hours=value),
        "d": timedelta(days=value),
    }[unit]


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_mod_log(
        self,
        guild: discord.Guild,
        *,
        colour: int,
        title: str,
        fields: list[tuple[str, str, bool]],
        thumbnail_url: str | None = None,
    ):
        """
        Build and send an embed to the #mod-logs channel.
        Looks up the channel by ID first, then falls back to searching by name.
        """
        channel = guild.get_channel(MOD_LOG_CHANNEL_ID) if MOD_LOG_CHANNEL_ID else None
        if not channel:
            channel = discord.utils.get(guild.text_channels, name=MOD_LOG_CHANNEL_NAME)
        if not channel:
            return

        embed = discord.Embed(title=title, colour=colour, timestamp=datetime.now(timezone.utc))
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass  # Bot lacks permissions in the log channel — fail silently

    # ── /ban ──────────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["ban"], description="Ban a member from the server")
    @app_commands.describe(
        member="Member to ban",
        reason="Reason for the ban",
        delete_days="Days of messages to delete (0–7)",
    )
    @has_any_role(*PERMS["ban"])
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
        delete_days: app_commands.Range[int, 0, 7] = 0,
    ):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message(
                "❌ You cannot ban someone with an equal or higher role.", ephemeral=True
            )

        await interaction.response.defer()

        try:
            await member.send(
                f"🔨 You have been **banned** from **{interaction.guild.name}**.\n**Reason:** {reason}"
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        try:
            await member.ban(reason=f"{interaction.user} | {reason}", delete_message_days=delete_days)
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ I don't have permission to ban that member.", ephemeral=True
            )

        fields = [
            ("User",      f"{member} (`{member.id}`)", False),
            ("Moderator", interaction.user.mention,    True),
            ("Reason",    reason,                      False),
        ]
        embed = discord.Embed(title="🔨 Member Banned", colour=0x8B0000)
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

        await interaction.followup.send(embed=embed)
        await self.send_mod_log(
            interaction.guild, colour=0x8B0000, title="🔨 Member Banned",
            fields=fields, thumbnail_url=member.display_avatar.url,
        )

    # ── /unban ────────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["unban"], description="Unban a user by their Discord ID")
    @app_commands.describe(user_id="The user's ID to unban", reason="Reason for unban")
    @has_any_role(*PERMS["unban"])
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
        try:
            uid = int(user_id)
        except ValueError:
            return await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)

        try:
            user = await self.bot.fetch_user(uid)
            await interaction.guild.unban(user, reason=f"{interaction.user} | {reason}")

            fields = [
                ("User",      f"`{user}` (`{user.id}`)", False),
                ("Moderator", interaction.user.mention,  True),
                ("Reason",    reason,                    False),
            ]
            embed = discord.Embed(title="✅ Member Unbanned", colour=0x2ECC71)
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)

            await interaction.response.send_message(embed=embed)
            await self.send_mod_log(
                interaction.guild, colour=0x2ECC71, title="✅ Member Unbanned", fields=fields
            )
        except discord.NotFound:
            await interaction.response.send_message("❌ That user is not banned.", ephemeral=True)

    # ── /kick ─────────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["kick"], description="Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for the kick")
    @has_any_role(*PERMS["kick"])
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message(
                "❌ You cannot kick someone with an equal or higher role.", ephemeral=True
            )

        # Defer first so we have time for the DM + kick without hitting the 3s interaction timeout
        await interaction.response.defer()

        try:
            await member.send(
                f"👢 You have been **kicked** from **{interaction.guild.name}**.\n**Reason:** {reason}"
            )
        except (discord.Forbidden, discord.HTTPException):
            pass  # DMs off, or rate limited — don't block the kick

        try:
            await member.kick(reason=f"{interaction.user} | {reason}")
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ I don't have permission to kick that member.", ephemeral=True
            )

        fields = [
            ("User",      f"{member} (`{member.id}`)", False),
            ("Moderator", interaction.user.mention,    True),
            ("Reason",    reason,                      False),
        ]
        embed = discord.Embed(title="👢 Member Kicked", colour=0xFF6B6B)
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

        await interaction.followup.send(embed=embed)
        await self.send_mod_log(
            interaction.guild, colour=0xFF6B6B, title="👢 Member Kicked",
            fields=fields, thumbnail_url=member.display_avatar.url,
        )

    # ── /mute ─────────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["mute"], description="Timeout a member (e.g. 10m, 2h, 1d)")
    @app_commands.describe(
        member="Member to mute",
        duration="Duration e.g. 10m, 2h, 1d (max 28d)",
        reason="Reason for the mute",
    )
    @has_any_role(*PERMS["mute"])
    async def mute(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: str,
        reason: str = "No reason provided",
    ):
        delta = parse_duration(duration)
        if not delta:
            return await interaction.response.send_message(
                "❌ Invalid duration. Use formats like `10m`, `2h`, `1d`.", ephemeral=True
            )
        if delta.total_seconds() > 28 * 86400:
            return await interaction.response.send_message(
                "❌ Maximum timeout duration is 28 days.", ephemeral=True
            )

        await member.timeout(delta, reason=f"{interaction.user} | {reason}")

        fields = [
            ("User",      f"{member.mention} (`{member}`)", False),
            ("Duration",  duration,                         True),
            ("Moderator", interaction.user.mention,         True),
            ("Reason",    reason,                           False),
        ]
        embed = discord.Embed(title="🔇 Member Muted", colour=0xF39C12)
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

        await interaction.response.send_message(embed=embed)
        await self.send_mod_log(
            interaction.guild, colour=0xF39C12, title="🔇 Member Muted",
            fields=fields, thumbnail_url=member.display_avatar.url,
        )

    # ── /unmute ───────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["unmute"], description="Remove timeout from a member")
    @app_commands.describe(member="Member to unmute", reason="Reason for removal")
    @has_any_role(*PERMS["unmute"])
    async def unmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        # Passing None to timeout() removes any active timeout
        await member.timeout(None, reason=f"{interaction.user} | {reason}")

        fields = [
            ("User",      f"{member.mention} (`{member}`)", False),
            ("Moderator", interaction.user.mention,         True),
        ]
        embed = discord.Embed(title="🔊 Member Unmuted", colour=0x2ECC71)
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

        await interaction.response.send_message(embed=embed)
        await self.send_mod_log(interaction.guild, colour=0x2ECC71, title="🔊 Member Unmuted", fields=fields)

    # ── /warn ─────────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["warn"], description="Issue a warning to a member")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @has_any_role(*PERMS["warn"])
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        # Append the reason and get the updated warning count for this member
        warnings[interaction.guild.id][member.id].append(reason)
        count = len(warnings[interaction.guild.id][member.id])

        try:
            await member.send(
                f"⚠️ You have been **warned** in **{interaction.guild.name}**.\n"
                f"**Reason:** {reason}\n**Total warnings:** {count}"
            )
        except discord.Forbidden:
            pass

        fields = [
            ("User",           f"{member.mention} (`{member}`)", False),
            ("Reason",         reason,                           False),
            ("Total Warnings", str(count),                       True),
            ("Moderator",      interaction.user.mention,         True),
        ]
        embed = discord.Embed(title="⚠️ Warning Issued", colour=0xF39C12)
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

        await interaction.response.send_message(embed=embed)
        await self.send_mod_log(
            interaction.guild, colour=0xF39C12, title="⚠️ Warning Issued",
            fields=fields, thumbnail_url=member.display_avatar.url,
        )

    # ── /warnings ─────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["warnings"], description="View a member's warnings")
    @app_commands.describe(member="Member to check")
    @has_any_role(*PERMS["warnings"])
    async def view_warnings(self, interaction: discord.Interaction, member: discord.Member):
        user_warns = warnings[interaction.guild.id][member.id]
        embed = discord.Embed(title=f"⚠️ Warnings for {member}", colour=0xF39C12)

        if not user_warns:
            embed.description = "No warnings on record."
        else:
            for i, reason in enumerate(user_warns, 1):
                embed.add_field(name=f"Warning {i}", value=reason, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /clearwarns ───────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["clearwarns"], description="Clear all warnings for a member")
    @app_commands.describe(member="Member to clear warnings for")
    @has_any_role(*PERMS["clearwarns"])
    async def clear_warnings(self, interaction: discord.Interaction, member: discord.Member):
        warnings[interaction.guild.id][member.id].clear()
        await interaction.response.send_message(
            f"✅ Cleared all warnings for {member.mention}.", ephemeral=True
        )
        await self.send_mod_log(
            interaction.guild, colour=0x2ECC71, title="🧹 Warnings Cleared",
            fields=[
                ("User",      f"{member.mention} (`{member}`)", False),
                ("Moderator", interaction.user.mention,         True),
            ],
        )

    # ── /purge ────────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["purge"], description="Bulk delete messages in this channel")
    @app_commands.describe(
        amount="Number of messages to delete (1–500)",
        user="Only delete messages from this user (optional)",
    )
    @has_any_role(*PERMS["purge"])
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 500],
        user: discord.Member = None,
    ):
        await interaction.response.defer(ephemeral=True)

        # Optional filter: only delete messages from a specific user
        def check(m: discord.Message):
            return user is None or m.author == user

        deleted = await interaction.channel.purge(limit=amount, check=check)
        await interaction.followup.send(
            f"✅ Deleted **{len(deleted)}** message(s)"
            + (f" from {user.mention}" if user else "") + ".",
            ephemeral=True,
        )
        await self.send_mod_log(
            interaction.guild, colour=0xE74C3C, title="🗑️ Messages Purged",
            fields=[
                ("Channel",       interaction.channel.mention,      True),
                ("Count",         str(len(deleted)),                True),
                ("Moderator",     interaction.user.mention,         True),
                ("Filtered User", user.mention if user else "None", True),
            ],
        )

    # ── /lock ─────────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["lock"], description="Lock this channel so @everyone cannot send messages")
    @app_commands.describe(reason="Reason for the lock")
    @has_any_role(*PERMS["lock"])
    async def lock(self, interaction: discord.Interaction, reason: str = "No reason provided"):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(
            interaction.guild.default_role, overwrite=overwrite, reason=reason
        )

        embed = discord.Embed(
            title="🔒 Channel Locked",
            description=f"{interaction.channel.mention} has been locked.\n**Reason:** {reason}",
            colour=0xE74C3C,
        )
        await interaction.response.send_message(embed=embed)
        await self.send_mod_log(
            interaction.guild, colour=0xE74C3C, title="🔒 Channel Locked",
            fields=[
                ("Channel",   interaction.channel.mention, True),
                ("Reason",    reason,                      False),
                ("Moderator", interaction.user.mention,    True),
            ],
        )

    # ── /unlock ───────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["unlock"], description="Unlock this channel")
    @has_any_role(*PERMS["unlock"])
    async def unlock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None  # Reset to default (inherit)
        await interaction.channel.set_permissions(
            interaction.guild.default_role, overwrite=overwrite
        )

        embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description=f"{interaction.channel.mention} is now unlocked.",
            colour=0x2ECC71,
        )
        await interaction.response.send_message(embed=embed)
        await self.send_mod_log(
            interaction.guild, colour=0x2ECC71, title="🔓 Channel Unlocked",
            fields=[
                ("Channel",   interaction.channel.mention, True),
                ("Moderator", interaction.user.mention,    True),
            ],
        )

    # ── /slowmode ─────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["slowmode"], description="Set slowmode delay for this channel")
    @app_commands.describe(seconds="Delay in seconds (0 to disable, max 21600)")
    @has_any_role(*PERMS["slowmode"])
    async def slowmode(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
        await interaction.channel.edit(slowmode_delay=seconds)
        msg = "✅ Slowmode disabled." if seconds == 0 else f"✅ Slowmode set to **{seconds}s**."
        await interaction.response.send_message(msg, ephemeral=True)
        await self.send_mod_log(
            interaction.guild, colour=0x3498DB, title="🐢 Slowmode Changed",
            fields=[
                ("Channel",   interaction.channel.mention, True),
                ("Delay",     f"{seconds}s",               True),
                ("Moderator", interaction.user.mention,    True),
            ],
        )

    # ── /nick ─────────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["nick"], description="Change a member's nickname")
    @app_commands.describe(member="Member to rename", nickname="New nickname (leave empty to reset)")
    @has_any_role(*PERMS["nick"])
    async def nick(self, interaction: discord.Interaction, member: discord.Member, nickname: str = None):
        old_nick = member.nick or member.name
        await member.edit(nick=nickname)

        embed = discord.Embed(title="📝 Nickname Changed", colour=0x3498DB)
        embed.add_field(name="User",   value=member.mention,            inline=False)
        embed.add_field(name="Before", value=old_nick,                   inline=True)
        embed.add_field(name="After",  value=nickname or member.name,   inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await self.send_mod_log(
            interaction.guild, colour=0x3498DB, title="📝 Nickname Changed",
            fields=[
                ("User",      f"{member.mention} (`{member}`)", False),
                ("Before",    old_nick,                         True),
                ("After",     nickname or member.name,          True),
                ("Moderator", interaction.user.mention,         True),
            ],
        )

    # ── Error handler ─────────────────────────────────────────────────────────

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have the required role.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
