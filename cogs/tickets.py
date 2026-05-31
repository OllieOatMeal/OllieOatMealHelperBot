# ══════════════════════════════════════════════════════════════════════════════
# cogs/tickets.py — Ticket system with embeds and buttons
# ══════════════════════════════════════════════════════════════════════════════
#
# HOW IT WORKS:
#   1. A moderator runs /ticket-panel in any channel to post the open-a-ticket embed.
#   2. Users click "Open Ticket" — a private channel is created under the ticket category.
#   3. Inside the ticket, a control panel embed shows Close / Claim / Add User buttons.
#   4. On close, a plaintext transcript is saved and posted to #mod-logs,
#      then the channel is deleted after a short delay.
#
# SETUP (in config.py):
#   TICKET_CATEGORY_NAME    — name of the category tickets are created under
#   TICKET_LOG_CHANNEL_NAME — channel where transcripts & events are logged (mod-logs)
#   TICKET_SUPPORT_ROLE_ID  — role that can always see and manage ticket channels

import asyncio
import io
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from config import (
    has_any_role,
    TICKET_CATEGORY_NAME, TICKET_LOG_CHANNEL_NAME, TICKET_SUPPORT_ROLE_ID,
    MOD_LOG_CHANNEL_ID, MOD_LOG_CHANNEL_NAME, HEAD_ADMIN_ROLE_ID
)

# ── Ticket counter (resets on restart — swap for a DB/JSON file for persistence) ──
_ticket_counter: dict[int, int] = {}


def next_ticket_number(guild_id: int) -> int:
    _ticket_counter[guild_id] = _ticket_counter.get(guild_id, 0) + 1
    return _ticket_counter[guild_id]


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

async def _get_log_channel(guild: discord.Guild) -> discord.TextChannel | None:
    return discord.utils.get(guild.text_channels, name=TICKET_LOG_CHANNEL_NAME)


async def _send_ticket_log(guild, *, colour, title, fields, thumbnail=None):
    ch = await _get_log_channel(guild)
    if not ch:
        return
    embed = discord.Embed(title=title, colour=colour, timestamp=datetime.now(timezone.utc))
    for name, value, inline in fields:
        embed.add_field(name=name, value=value, inline=inline)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    try:
        await ch.send(embed=embed)
    except discord.Forbidden:
        pass


def _is_staff(member: discord.Member) -> bool:
    return any(r.id in (TICKET_SUPPORT_ROLE_ID) for r in member.roles)


# ════════════════════════════════════════════════════════════════════════════
# Views / Modals
# ════════════════════════════════════════════════════════════════════════════

class OpenTicketView(discord.ui.View):
    """Persistent view posted by /ticket-panel."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open a Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="ticket:open",
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user

        # Prevent duplicate tickets
        existing = discord.utils.find(
            lambda c: c.name.startswith("ticket-") and str(member.id) in (c.topic or ""),
            guild.text_channels,
        )
        if existing:
            return await interaction.response.send_message(
                f"❌ You already have an open ticket: {existing.mention}", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        number = next_ticket_number(guild.id)
        support_role = guild.get_role(TICKET_SUPPORT_ROLE_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True
            ),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, manage_messages=True
            )

        safe_name = member.name.lower().replace(" ", "-")[:20]
        channel = await guild.create_text_channel(
            name=f"ticket-{number:04d}-{safe_name}",
            category=category,
            overwrites=overwrites,
            topic=f"Opened by {member} | ID: {member.id}",
        )

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=(
                f"Welcome {member.mention}! Staff will be with you shortly.\n\n"
                "Please describe your issue in as much detail as possible."
            ),
            colour=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Ticket #{number:04d} • {guild.name}")
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)

        ping = member.mention + (f" | {support_role.mention}" if support_role else "")
        await channel.send(content=ping, embed=embed, view=TicketControlView())

        await interaction.followup.send(f"✅ Ticket opened: {channel.mention}", ephemeral=True)
        await _send_ticket_log(
            guild, colour=0x5865F2, title="🎫 Ticket Opened",
            fields=[
                ("User", f"{member.mention} (`{member}`)", True),
                ("Channel", channel.mention, True),
                ("Ticket #", f"{number:04d}", True),
            ],
            thumbnail=member.display_avatar.url,
        )


class TicketControlView(discord.ui.View):
    """Persistent view pinned inside each ticket channel."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        guild = interaction.guild
        topic = channel.topic or ""
        is_opener = str(interaction.user.id) in topic

        if not (_is_staff(interaction.user) or is_opener):
            return await interaction.response.send_message(
                "❌ Only staff or the ticket opener can close this.", ephemeral=True
            )

        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔒 Closing Ticket",
                description="Saving transcript and deleting channel in **5 seconds**.",
                colour=0xE74C3C,
            )
        )

        # Build transcript
        lines = [
            f"Transcript: {channel.name}",
            f"Closed by:  {interaction.user} ({interaction.user.id})",
            f"Date:       {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "=" * 60,
        ]
        async for msg in channel.history(limit=500, oldest_first=True):
            ts = msg.created_at.strftime("%H:%M")
            lines.append(f"[{ts}] {msg.author}: {msg.content or '(no text)'}")
            for att in msg.attachments:
                lines.append(f"        [Attachment] {att.url}")

        transcript_file = discord.File(
            io.BytesIO("\n".join(lines).encode("utf-8")),
            filename=f"{channel.name}-transcript.txt",
        )

        log_ch = await _get_log_channel(guild)
        if log_ch:
            close_embed = discord.Embed(
                title="🔒 Ticket Closed",
                colour=0xE74C3C,
                timestamp=datetime.now(timezone.utc),
            )
            close_embed.add_field(name="Channel", value=channel.name, inline=True)
            close_embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
            if topic:
                close_embed.add_field(name="Info", value=topic, inline=False)
            try:
                await log_ch.send(embed=close_embed, file=transcript_file)
            except discord.Forbidden:
                pass

        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Ticket closed by {interaction.user}")
        except discord.NotFound:
            pass

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success, emoji="✋", custom_id="ticket:claim")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _is_staff(interaction.user):
            return await interaction.response.send_message("❌ Only staff can claim tickets.", ephemeral=True)

        embed = discord.Embed(
            title="✋ Ticket Claimed",
            description=f"This ticket is now being handled by {interaction.user.mention}.",
            colour=0x2ECC71,
            timestamp=datetime.now(timezone.utc),
        )
        await interaction.response.send_message(embed=embed)
        await _send_ticket_log(
            interaction.guild, colour=0x2ECC71, title="✋ Ticket Claimed",
            fields=[
                ("Channel", interaction.channel.mention, True),
                ("Claimed By", interaction.user.mention, True),
            ],
        )

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.secondary, emoji="➕", custom_id="ticket:adduser")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _is_staff(interaction.user):
            return await interaction.response.send_message("❌ Only staff can add users.", ephemeral=True)
        await interaction.response.send_modal(AddUserModal(interaction.channel))


class AddUserModal(discord.ui.Modal, title="Add User to Ticket"):
    user_id_input = discord.ui.TextInput(
        label="User ID",
        placeholder="Right-click the user → Copy ID",
        min_length=17,
        max_length=20,
    )

    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid = int(self.user_id_input.value.strip())
            member = interaction.guild.get_member(uid) or await interaction.guild.fetch_member(uid)
        except (ValueError, discord.NotFound):
            return await interaction.response.send_message("❌ User not found.", ephemeral=True)

        await self.channel.set_permissions(
            member,
            view_channel=True, send_messages=True, read_message_history=True,
        )
        await interaction.response.send_message(f"✅ Added {member.mention}.", ephemeral=True)
        await self.channel.send(
            embed=discord.Embed(
                description=f"➕ {member.mention} was added by {interaction.user.mention}.",
                colour=0x5865F2,
            )
        )


# ════════════════════════════════════════════════════════════════════════════
# Cog
# ════════════════════════════════════════════════════════════════════════════

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(OpenTicketView())
        bot.add_view(TicketControlView())

    @app_commands.command(name="basic-ticket-panel", description="Post the basic ticket creation panel in this channel")
    @has_any_role(HEAD_ADMIN_ROLE_ID)
    async def ticket_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 Support Tickets",
            description=(
                "Need help or want to report something?\n\n"
                "Click **Open a Ticket** below to create a private support channel.\n"
                "Our staff team will assist you as soon as possible."
            ),
            colour=0x5865F2,
        )
        embed.set_footer(text=interaction.guild.name)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        await interaction.channel.send(embed=embed, view=OpenTicketView())
        await interaction.response.send_message("✅ Ticket panel posted.", ephemeral=True)
    
    @app_commands.command(name="cc-ticket-panel", description="Post the content creator ticket creation panel in this channel")
    @has_any_role(HEAD_ADMIN_ROLE_ID)
    async def ticket_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎥 Content Creator Tickets",
            description=(
                "Wish to apply for the content creator role?\n\n"
                "Click **Open a Ticket** below to create a private support channel.\n"
                "Our staff team will assist you as soon as possible."
            ),
            colour=0x5865F2,
        )
        embed.set_footer(text=interaction.guild.name)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        await interaction.channel.send(embed=embed, view=OpenTicketView())
        await interaction.response.send_message("✅ Ticket panel posted.", ephemeral=True)

    @app_commands.command(name="ticket-close", description="Force-close the current ticket channel")
    @has_any_role(TICKET_SUPPORT_ROLE_ID)
    async def ticket_close(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(
                "❌ This must be used inside a ticket channel.", ephemeral=True
            )
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔒 Force Closing",
                description=f"Closed by {interaction.user.mention}. Deleting in 5 seconds.",
                colour=0xE74C3C,
            )
        )
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Force-closed by {interaction.user}")
        except discord.NotFound:
            pass

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have the required role.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
