"""
cogs/modmail.py
────────────────
Modmail system — users DM the bot to open a thread with staff.

Flow:
  1. A user DMs the bot any message
  2. The bot creates a private channel in the modmail category (mirroring tickets)
  3. Everything the user sends in DMs is relayed to that channel, and vice versa
  4. Staff can claim, forward, or close the thread
  5. On close, a transcript is saved and logged to #ticket-logs

Commands (Admin+ required):
  /modmail-panel — Post a panel telling users how to contact staff via DM

Buttons (available inside a modmail channel):
  Claim   — Assign yourself as the handler
  Forward — Forward the thread to Head Admin
  Close   — Close, save transcript, and DM the user a summary
"""

import asyncio
import io
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from cogs.blacklist import is_blacklisted
from config import (
    has_any_role,
    TICKET_CATEGORY_NAME, TICKET_LOG_CHANNEL_NAME, TICKET_SUPPORT_ROLE_ID,
    HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID,
)

# guild_id -> {user_id -> channel_id}  (in-memory; survives restarts via channel topic)
_open_threads: dict[int, dict[int, int]] = {}

MODMAIL_CATEGORY_NAME = TICKET_CATEGORY_NAME   # reuse the same category


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_staff(member: discord.Member) -> bool:
    return any(r.id in (TICKET_SUPPORT_ROLE_ID, HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
               for r in member.roles)


async def _get_log_channel(guild: discord.Guild) -> discord.TextChannel | None:
    return discord.utils.get(guild.text_channels, name=TICKET_LOG_CHANNEL_NAME)


async def _send_log(guild, *, colour, title, fields, thumbnail=None):
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


def _parse_user_id(channel: discord.TextChannel) -> int | None:
    """Extract the user ID stored in the channel topic."""
    topic = channel.topic or ""
    if "ID:" in topic:
        try:
            return int(topic.split("ID:")[-1].strip())
        except ValueError:
            pass
    return None


# ── Views ──────────────────────────────────────────────────────────────────────

class ModmailPanelView(discord.ui.View):
    """Persistent view posted by /modmail-panel."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Contact Staff",
        style=discord.ButtonStyle.primary,
        emoji="✉️",
        custom_id="modmail:instructions",
    )
    async def contact_staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="✉️ How to Contact Staff",
                description=(
                    "To open a modmail thread, simply **DM this bot** any message.\n\n"
                    "A private channel will be created where staff can assist you.\n"
                    "Please describe your issue clearly in your first message."
                ),
                colour=0x5865F2,
            ),
            ephemeral=True,
        )


class ModmailControlView(discord.ui.View):
    """Persistent view pinned inside each modmail channel."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="modmail:close")
    async def close_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        guild = interaction.guild

        if not _is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can close modmail threads.", ephemeral=True
            )

        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔒 Closing Thread",
                description="Saving transcript and closing in **5 seconds**.",
                colour=0xE74C3C,
            )
        )

        # Build transcript
        lines = [
            f"Modmail transcript: {channel.name}",
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

        # Log it
        log_ch = await _get_log_channel(guild)
        if log_ch:
            close_embed = discord.Embed(
                title="🔒 Modmail Closed",
                colour=0xE74C3C,
                timestamp=datetime.now(timezone.utc),
            )
            close_embed.add_field(name="Channel", value=channel.name, inline=True)
            close_embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
            if channel.topic:
                close_embed.add_field(name="Info", value=channel.topic, inline=False)
            try:
                await log_ch.send(embed=close_embed, file=transcript_file)
            except discord.Forbidden:
                pass

        # DM the user that their thread was closed
        user_id = _parse_user_id(channel)
        if user_id:
            try:
                user = await interaction.client.fetch_user(user_id)
                await user.send(
                    embed=discord.Embed(
                        title="🔒 Modmail Thread Closed",
                        description=(
                            f"Your modmail thread in **{guild.name}** has been closed by staff.\n"
                            "Feel free to DM again if you need further help."
                        ),
                        colour=0xE74C3C,
                        timestamp=datetime.now(timezone.utc),
                    )
                )
            except (discord.NotFound, discord.Forbidden):
                pass

            # Clean up in-memory tracking
            _open_threads.get(guild.id, {}).pop(user_id, None)

        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Modmail closed by {interaction.user}")
        except discord.NotFound:
            pass

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success, emoji="✋", custom_id="modmail:claim")
    async def claim_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _is_staff(interaction.user):
            return await interaction.response.send_message("❌ Only staff can claim threads.", ephemeral=True)

        embed = discord.Embed(
            title="✋ Thread Claimed",
            description=f"This modmail thread is now being handled by {interaction.user.mention}.",
            colour=0x2ECC71,
            timestamp=datetime.now(timezone.utc),
        )
        await interaction.response.send_message(embed=embed)
        await _send_log(
            interaction.guild, colour=0x2ECC71, title="✋ Modmail Claimed",
            fields=[
                ("Channel", interaction.channel.mention, True),
                ("Claimed By", interaction.user.mention, True),
            ],
        )

    @discord.ui.button(label="Forward", style=discord.ButtonStyle.secondary, emoji="↗️", custom_id="modmail:forward")
    async def forward_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _is_staff(interaction.user):
            return await interaction.response.send_message("❌ Only staff can forward threads.", ephemeral=True)
        await interaction.response.send_message(
            "Select a role to forward this thread to:",
            view=ForwardRoleSelect(interaction.channel),
            ephemeral=True,
        )


class ForwardRoleSelect(discord.ui.View):
    """Dropdown to pick which role to forward the modmail to."""

    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=60)
        self.channel = channel

    @discord.ui.select(
        placeholder="Choose a role to forward to...",
        options=[
            discord.SelectOption(label="Head Admin", value="HEAD_ADMIN"),
        ],
        custom_id="modmail:forward:role_select",
    )
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        channel = self.channel

        role_map = {"HEAD_ADMIN": HEAD_ADMIN_ROLE_ID}
        target_role = guild.get_role(role_map[select.values[0]])

        if not target_role:
            return await interaction.followup.send("❌ Target role not found.", ephemeral=True)

        try:
            # Remove individual member overwrites except the user and bot
            user_id = _parse_user_id(channel)
            for target, overwrite in list(channel.overwrites.items()):
                if isinstance(target, discord.Member):
                    if user_id and target.id == user_id:
                        continue
                    if target.id == guild.me.id:
                        continue
                    await channel.set_permissions(target, overwrite=None)

            await channel.set_permissions(
                target_role,
                view_channel=True, send_messages=True,
                read_message_history=True, manage_messages=True,
            )

            forward_embed = discord.Embed(
                title="↗️ Thread Forwarded",
                description=f"This modmail has been forwarded to {target_role.mention}.",
                colour=0xF39C12,
                timestamp=datetime.now(timezone.utc),
            )
            forward_embed.add_field(name="Forwarded By", value=interaction.user.mention, inline=True)
            await channel.send(content=target_role.mention, embed=forward_embed)

            await _send_log(
                guild, colour=0xF39C12, title="↗️ Modmail Forwarded",
                fields=[
                    ("Channel", channel.mention, True),
                    ("Forwarded To", target_role.mention, True),
                    ("Forwarded By", interaction.user.mention, True),
                ],
            )
            await interaction.followup.send(f"✅ Forwarded to {target_role.mention}.", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("❌ Missing permissions to modify this channel.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {e}", ephemeral=True)


# ── Cog ────────────────────────────────────────────────────────────────────────

class Modmail(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(ModmailPanelView())
        bot.add_view(ModmailControlView())

    # ── DM listener ───────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Only handle DMs, ignore bots
        if message.author.bot:
            return
        if message.guild is not None:
            return

        user = message.author

        # Check blacklist against the first guild the bot shares with the user
        guild = next((g for g in self.bot.guilds if g.get_member(user.id)), None)
        if not guild:
            return

        if await is_blacklisted(user.id, "tickets"):
            try:
                await user.send("🚫 You are blacklisted from contacting staff.")
            except discord.Forbidden:
                pass
            return

        # Find or create the modmail channel
        threads = _open_threads.setdefault(guild.id, {})
        channel_id = threads.get(user.id)
        channel = guild.get_channel(channel_id) if channel_id else None

        # Also scan existing channels in case bot restarted (topic fallback)
        if not channel:
            channel = discord.utils.find(
                lambda c: c.name.startswith("modmail-") and str(user.id) in (c.topic or ""),
                guild.text_channels,
            )
            if channel:
                threads[user.id] = channel.id

        if not channel:
            channel = await self._open_thread(guild, user)
            if not channel:
                return
            threads[user.id] = channel.id

        # Relay the DM to the modmail channel
        relay_embed = discord.Embed(
            description=message.content or "(no text)",
            colour=0x5865F2,
            timestamp=message.created_at,
        )
        relay_embed.set_author(name=str(user), icon_url=user.display_avatar.url)

        files = [await att.to_file() for att in message.attachments]
        try:
            await channel.send(embed=relay_embed, files=files)
        except discord.Forbidden:
            pass

        # Acknowledge receipt to the user
        try:
            await message.add_reaction("✅")
        except discord.Forbidden:
            pass

    # ── Staff → User relay ────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):  # noqa: F811  (handled below)
        pass  # placeholder — see _dispatch below

    async def cog_load(self):
        # Replace the duplicate listener with a single dispatcher
        self.bot.remove_listener(self.on_message, "on_message")
        self.bot.add_listener(self._dispatch_message, "on_message")

    async def _dispatch_message(self, message: discord.Message):
        if message.author.bot:
            return

        # DM → channel
        if message.guild is None:
            await self._handle_dm(message)
            return

        # Channel → DM (staff reply)
        if message.channel.name.startswith("modmail-"):
            await self._handle_staff_reply(message)

    async def _handle_dm(self, message: discord.Message):
        user = message.author
        guild = next((g for g in self.bot.guilds if g.get_member(user.id)), None)
        if not guild:
            return

        if await is_blacklisted(user.id, "tickets"):
            try:
                await user.send("🚫 You are blacklisted from contacting staff.")
            except discord.Forbidden:
                pass
            return

        threads = _open_threads.setdefault(guild.id, {})
        channel_id = threads.get(user.id)
        channel = guild.get_channel(channel_id) if channel_id else None

        if not channel:
            channel = discord.utils.find(
                lambda c: c.name.startswith("modmail-") and str(user.id) in (c.topic or ""),
                guild.text_channels,
            )
            if channel:
                threads[user.id] = channel.id

        if not channel:
            channel = await self._open_thread(guild, user)
            if not channel:
                return
            threads[user.id] = channel.id

        relay_embed = discord.Embed(
            description=message.content or "(no text)",
            colour=0x5865F2,
            timestamp=message.created_at,
        )
        relay_embed.set_author(name=f"{user} (User)", icon_url=user.display_avatar.url)

        files = [await att.to_file() for att in message.attachments]
        try:
            await channel.send(embed=relay_embed, files=files)
        except discord.Forbidden:
            pass

        try:
            await message.add_reaction("✅")
        except discord.Forbidden:
            pass

    async def _handle_staff_reply(self, message: discord.Message):
        """Relay a staff message in a modmail channel back to the user via DM."""
        # Ignore system messages and embeds-only (bot relays)
        if not message.content and not message.attachments:
            return

        channel = message.channel
        user_id = _parse_user_id(channel)
        if not user_id:
            return

        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            return

        reply_embed = discord.Embed(
            description=message.content or "(no text)",
            colour=0x2ECC71,
            timestamp=message.created_at,
        )
        reply_embed.set_author(
            name=f"{message.author.display_name} (Staff)",
            icon_url=message.author.display_avatar.url,
        )
        reply_embed.set_footer(text=message.guild.name)

        files = [await att.to_file() for att in message.attachments]
        try:
            await user.send(embed=reply_embed, files=files)
            await message.add_reaction("✅")
        except discord.Forbidden:
            await channel.send(
                embed=discord.Embed(
                    description=f"⚠️ Could not DM {user.mention} — they may have DMs disabled.",
                    colour=0xE74C3C,
                ),
                delete_after=10,
            )

    # ── Thread creation ────────────────────────────────────────────────────────

    async def _open_thread(self, guild: discord.Guild, user: discord.User) -> discord.TextChannel | None:
        category = discord.utils.get(guild.categories, name=MODMAIL_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(MODMAIL_CATEGORY_NAME)

        support_role = guild.get_role(TICKET_SUPPORT_ROLE_ID)
        safe_name = user.name.lower().replace(" ", "-")[:20]

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True
            ),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, manage_messages=True,
            )

        channel = await guild.create_text_channel(
            name=f"modmail-{safe_name}",
            category=category,
            overwrites=overwrites,
            topic=f"Modmail from {user} | ID: {user.id}",
        )

        # Opening embed in the channel
        embed = discord.Embed(
            title="✉️ New Modmail",
            description=(
                f"**User:** {user.mention} (`{user}`)\n"
                f"**ID:** `{user.id}`\n\n"
                "Messages sent in this channel will be relayed to the user via DM.\n"
                "Messages the user sends will appear here automatically."
            ),
            colour=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=guild.name)

        ping = support_role.mention if support_role else ""
        await channel.send(content=ping, embed=embed, view=ModmailControlView())

        # DM the user to confirm the thread is open
        try:
            await user.send(
                embed=discord.Embed(
                    title="✉️ Modmail Thread Opened",
                    description=(
                        f"Your message has been received by **{guild.name}** staff.\n"
                        "Continue sending messages here and staff will reply shortly."
                    ),
                    colour=0x5865F2,
                    timestamp=datetime.now(timezone.utc),
                )
            )
        except discord.Forbidden:
            pass

        await _send_log(
            guild, colour=0x5865F2, title="✉️ Modmail Opened",
            fields=[
                ("User", f"{user.mention} (`{user}`)", True),
                ("Channel", channel.mention, True),
            ],
            thumbnail=user.display_avatar.url,
        )

        return channel

    # ── Slash commands ─────────────────────────────────────────────────────────

    @app_commands.command(name="modmail-panel", description="Post the modmail contact panel in this channel")
    @has_any_role(HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
    async def modmail_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="✉️ Contact Staff",
            description=(
                "Need help, want to report something, or have a question for staff?\n\n"
                "Click the button below for instructions, or simply **DM this bot** directly.\n"
                "A private thread will be created and our team will get back to you."
            ),
            colour=0x5865F2,
        )
        embed.set_footer(text=interaction.guild.name)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        await interaction.channel.send(embed=embed, view=ModmailPanelView())
        await interaction.response.send_message("✅ Modmail panel posted.", ephemeral=True)

    @app_commands.command(name="modmail-close", description="Force-close the current modmail thread")
    @has_any_role(TICKET_SUPPORT_ROLE_ID, HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
    async def modmail_close(self, interaction: discord.Interaction):
        if not interaction.channel.name.startswith("modmail-"):
            return await interaction.response.send_message(
                "❌ This must be used inside a modmail channel.", ephemeral=True
            )

        user_id = _parse_user_id(interaction.channel)
        if user_id:
            _open_threads.get(interaction.guild.id, {}).pop(user_id, None)
            try:
                user = await self.bot.fetch_user(user_id)
                await user.send(
                    embed=discord.Embed(
                        title="🔒 Modmail Thread Closed",
                        description=(
                            f"Your modmail thread in **{interaction.guild.name}** has been closed.\n"
                            "Feel free to DM again if you need further help."
                        ),
                        colour=0xE74C3C,
                    )
                )
            except (discord.NotFound, discord.Forbidden):
                pass

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
    await bot.add_cog(Modmail(bot))