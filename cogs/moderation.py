# ══════════════════════════════════════════════════════════════════════════════
# cogs/moderation.py — Full moderation system
# ══════════════════════════════════════════════════════════════════════════════
#
# All commands use role ID checks from config.py:
#   Admin only     : /unban, /clearwarns, /lock, /unlock
#   Mod or Admin   : /ban, /kick, /mute, /unmute, /slowmode, /nick, /purge
#   Helper+        : /warn, /warnings

import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
from collections import defaultdict
import re
from config import has_any_role, ADMIN_ROLE_ID, MODERATOR_ROLE_ID, HELPER_ROLE_ID

# In-memory warning store: {guild_id: {user_id: [reason, ...]}}
warnings: dict[int, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))


def parse_duration(duration: str) -> timedelta | None:
    """Parse strings like '10m', '2h', '1d' into a timedelta."""
    match = re.fullmatch(r"(\d+)([smhd])", duration.strip().lower())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    return {"s": timedelta(seconds=value), "m": timedelta(minutes=value),
            "h": timedelta(hours=value),   "d": timedelta(days=value)}[unit]


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /ban ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(member="Member to ban", reason="Reason for the ban", delete_days="Days of messages to delete (0–7)")
    @has_any_role(MODERATOR_ROLE_ID, ADMIN_ROLE_ID)
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
        try:
            await member.send(f"🔨 You have been **banned** from **{interaction.guild.name}**.\n**Reason:** {reason}")
        except discord.Forbidden:
            pass
        await member.ban(reason=f"{interaction.user} | {reason}", delete_message_days=delete_days)
        embed = discord.Embed(title="🔨 Member Banned", colour=0x8B0000)
        embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /unban ────────────────────────────────────────────────────────────────
    @app_commands.command(name="unban", description="Unban a user by their ID")
    @app_commands.describe(user_id="The user's ID to unban", reason="Reason for unban")
    @has_any_role(ADMIN_ROLE_ID)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
        try:
            uid = int(user_id)
        except ValueError:
            return await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)
        try:
            user = await self.bot.fetch_user(uid)
            await interaction.guild.unban(user, reason=f"{interaction.user} | {reason}")
            embed = discord.Embed(title="✅ Member Unbanned", colour=0x2ECC71)
            embed.add_field(name="User", value=f"`{user}` (`{user.id}`)", inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.NotFound:
            await interaction.response.send_message("❌ That user is not banned.", ephemeral=True)

    # ── /kick ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for the kick")
    @has_any_role(MODERATOR_ROLE_ID, ADMIN_ROLE_ID)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message(
                "❌ You cannot kick someone with an equal or higher role.", ephemeral=True
            )
        try:
            await member.send(f"👢 You have been **kicked** from **{interaction.guild.name}**.\n**Reason:** {reason}")
        except discord.Forbidden:
            pass
        await member.kick(reason=f"{interaction.user} | {reason}")
        embed = discord.Embed(title="👢 Member Kicked", colour=0xFF6B6B)
        embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /mute ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="mute", description="Timeout a member (e.g. 10m, 2h, 1d)")
    @app_commands.describe(member="Member to mute", duration="Duration e.g. 10m, 2h, 1d (max 28d)", reason="Reason for the mute")
    @has_any_role(MODERATOR_ROLE_ID, ADMIN_ROLE_ID)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
        delta = parse_duration(duration)
        if not delta:
            return await interaction.response.send_message("❌ Invalid duration. Use formats like `10m`, `2h`, `1d`.", ephemeral=True)
        if delta.total_seconds() > 28 * 86400:
            return await interaction.response.send_message("❌ Maximum timeout duration is 28 days.", ephemeral=True)
        await member.timeout(delta, reason=f"{interaction.user} | {reason}")
        embed = discord.Embed(title="🔇 Member Muted", colour=0xF39C12)
        embed.add_field(name="User", value=f"{member.mention} (`{member}`)", inline=False)
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /unmute ───────────────────────────────────────────────────────────────
    @app_commands.command(name="unmute", description="Remove timeout from a member")
    @app_commands.describe(member="Member to unmute")
    @has_any_role(MODERATOR_ROLE_ID, ADMIN_ROLE_ID)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await member.timeout(None, reason=f"{interaction.user} | {reason}")
        embed = discord.Embed(title="🔊 Member Unmuted", colour=0x2ECC71)
        embed.add_field(name="User", value=f"{member.mention} (`{member}`)", inline=False)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /warn ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Issue a warning to a member")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @has_any_role(HELPER_ROLE_ID, MODERATOR_ROLE_ID, ADMIN_ROLE_ID)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        warnings[interaction.guild.id][member.id].append(reason)
        count = len(warnings[interaction.guild.id][member.id])
        try:
            await member.send(
                f"⚠️ You have been **warned** in **{interaction.guild.name}**.\n"
                f"**Reason:** {reason}\n**Total warnings:** {count}"
            )
        except discord.Forbidden:
            pass
        embed = discord.Embed(title="⚠️ Warning Issued", colour=0xF39C12)
        embed.add_field(name="User", value=f"{member.mention} (`{member}`)", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Total Warnings", value=str(count), inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /warnings ─────────────────────────────────────────────────────────────
    @app_commands.command(name="warnings", description="View a member's warnings")
    @app_commands.describe(member="Member to check")
    @has_any_role(HELPER_ROLE_ID, MODERATOR_ROLE_ID, ADMIN_ROLE_ID)
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
    @app_commands.command(name="clearwarns", description="Clear all warnings for a member")
    @app_commands.describe(member="Member to clear warnings for")
    @has_any_role(ADMIN_ROLE_ID)
    async def clear_warnings(self, interaction: discord.Interaction, member: discord.Member):
        warnings[interaction.guild.id][member.id].clear()
        await interaction.response.send_message(f"✅ Cleared all warnings for {member.mention}.", ephemeral=True)

    # ── /purge ────────────────────────────────────────────────────────────────
    @app_commands.command(name="purge", description="Bulk delete messages in this channel")
    @app_commands.describe(amount="Number of messages to delete (1–500)", user="Only delete messages from this user (optional)")
    @has_any_role(MODERATOR_ROLE_ID, ADMIN_ROLE_ID)
    async def purge(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 500], user: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        def check(m: discord.Message):
            return user is None or m.author == user
        deleted = await interaction.channel.purge(limit=amount, check=check)
        await interaction.followup.send(
            f"✅ Deleted **{len(deleted)}** message(s){f' from {user.mention}' if user else ''}.",
            ephemeral=True,
        )

    # ── /lock ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="lock", description="Lock this channel so @everyone cannot send messages")
    @app_commands.describe(reason="Reason for the lock")
    @has_any_role(ADMIN_ROLE_ID)
    async def lock(self, interaction: discord.Interaction, reason: str = "No reason provided"):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=reason)
        embed = discord.Embed(
            title="🔒 Channel Locked",
            description=f"{interaction.channel.mention} has been locked.\n**Reason:** {reason}",
            colour=0xE74C3C,
        )
        await interaction.response.send_message(embed=embed)

    # ── /unlock ───────────────────────────────────────────────────────────────
    @app_commands.command(name="unlock", description="Unlock this channel")
    @has_any_role(ADMIN_ROLE_ID)
    async def unlock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description=f"{interaction.channel.mention} is now unlocked.",
            colour=0x2ECC71,
        )
        await interaction.response.send_message(embed=embed)

    # ── /slowmode ─────────────────────────────────────────────────────────────
    @app_commands.command(name="slowmode", description="Set slowmode for this channel")
    @app_commands.describe(seconds="Slowmode in seconds (0 to disable, max 21600)")
    @has_any_role(MODERATOR_ROLE_ID, ADMIN_ROLE_ID)
    async def slowmode(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
        await interaction.channel.edit(slowmode_delay=seconds)
        msg = "✅ Slowmode disabled." if seconds == 0 else f"✅ Slowmode set to **{seconds}s**."
        await interaction.response.send_message(msg, ephemeral=True)

    # ── /nick ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="nick", description="Change a member's nickname")
    @app_commands.describe(member="Member to rename", nickname="New nickname (leave empty to reset)")
    @has_any_role(MODERATOR_ROLE_ID, ADMIN_ROLE_ID)
    async def nick(self, interaction: discord.Interaction, member: discord.Member, nickname: str = None):
        old_nick = member.nick or member.name
        await member.edit(nick=nickname)
        embed = discord.Embed(title="📝 Nickname Changed", colour=0x3498DB)
        embed.add_field(name="User", value=member.mention, inline=False)
        embed.add_field(name="Before", value=old_nick, inline=True)
        embed.add_field(name="After", value=nickname or member.name, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Error handler ─────────────────────────────────────────────────────────
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have the required role.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))