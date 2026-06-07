import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from config import has_any_role, OWNER_ROLE_ID, LOG_CHANNEL_NAME, LOG_CHANNEL_ID as _LOG_CHANNEL_ID

_log_channel_id = _LOG_CHANNEL_ID

COLOURS = {
    "join":     0x2ECC71,
    "leave":    0xE74C3C,
    "edit":     0xF39C12,
    "delete":   0xE74C3C,
    "ban":      0x8B0000,
    "unban":    0x2ECC71,
    "kick":     0xFF6B6B,
    "mute":     0xF39C12,
    "role":     0x9B59B6,
    "nick":     0x3498DB,
    "voice":    0x1ABC9C,
    "channel":  0x95A5A6,
    "command":  0x3498DB,
    "error":    0xFF0000,
    "reaction": 0xF1C40F,
    "default":  0x7289DA,
}


def truncate(text: str, limit: int = 1024) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


class Logging(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._log_channel: discord.TextChannel | None = None

    async def get_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        global _log_channel_id
        if self._log_channel and self._log_channel.guild == guild:
            return self._log_channel
        if _log_channel_id:
            ch = guild.get_channel(_log_channel_id)
        else:
            ch = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
        self._log_channel = ch
        return ch

    async def send_log(
        self,
        guild: discord.Guild,
        *,
        colour: int,
        title: str,
        fields: list[tuple[str, str, bool]] | None = None,
        thumbnail: str | None = None,
    ):
        ch = await self.get_log_channel(guild)
        if not ch:
            return
        embed = discord.Embed(title=title, colour=colour, timestamp=datetime.now(timezone.utc))
        for name, value, inline in fields or []:
            embed.add_field(name=name, value=truncate(value), inline=inline)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        try:
            await ch.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.content == after.content or not before.guild:
            return
        await self.send_log(
            before.guild,
            colour=COLOURS["edit"],
            title="✏️ Message Edited",
            fields=[
                ("Author", f"{before.author.mention} (`{before.author}`)", False),
                ("Channel", before.channel.mention, False),
                ("Before", truncate(before.content or "*empty*", 512), False),
                ("After", truncate(after.content or "*empty*", 512), False),
                ("Jump", f"[Go to message]({after.jump_url})", False),
            ],
        )

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        fields = [
            ("Author", f"{message.author.mention} (`{message.author}`)", False),
            ("Channel", message.channel.mention, False),
            ("Content", truncate(message.content or "*empty*", 512), False),
        ]
        if message.attachments:
            fields.append(("Attachments", "\n".join(a.filename for a in message.attachments), False))
        await self.send_log(
            message.guild, colour=COLOURS["delete"], title="🗑️ Message Deleted", fields=fields
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        age = (datetime.now(timezone.utc) - member.created_at).days
        await self.send_log(
            member.guild,
            colour=COLOURS["join"],
            title="📥 Member Joined",
            thumbnail=member.display_avatar.url,
            fields=[
                ("User", f"{member.mention} (`{member}`)", False),
                ("ID", str(member.id), True),
                ("Account Age", f"{age} days", True),
                ("Member Count", str(member.guild.member_count), True),
            ],
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        await self.send_log(
            member.guild,
            colour=COLOURS["leave"],
            title="📤 Member Left",
            thumbnail=member.display_avatar.url,
            fields=[
                ("User", f"`{member}`", False),
                ("ID", str(member.id), True),
                ("Roles", ", ".join(roles) or "None", False),
            ],
        )

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        await self.send_log(
            guild,
            colour=COLOURS["ban"],
            title="🔨 Member Banned",
            thumbnail=user.display_avatar.url,
            fields=[("User", f"`{user}` (`{user.id}`)", False)],
        )

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        await self.send_log(
            guild,
            colour=COLOURS["unban"],
            title="✅ Member Unbanned",
            fields=[("User", f"`{user}` (`{user.id}`)", False)],
        )

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        
        if before.nick != after.nick:
            await self.send_log(
                before.guild,
                colour=COLOURS["nick"],
                title="📝 Nickname Changed",
                thumbnail=after.display_avatar.url,
                fields=[
                    ("User", f"{after.mention} (`{after}`)", False),
                    ("Before", before.nick or "*none*", True),
                    ("After", after.nick or "*none*", True),
                ],
            )
        added   = [r for r in after.roles  if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]
        if added or removed:
            fields = [("User", f"{after.mention} (`{after}`)", False)]
            if added:
                fields.append(("Roles Added", ", ".join(r.mention for r in added), False))
            if removed:
                fields.append(("Roles Removed", ", ".join(r.mention for r in removed), False))
            await self.send_log(
                before.guild, colour=COLOURS["role"], title="🎭 Member Roles Updated", fields=fields
            )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel:
            return
        if not before.channel and after.channel:
            action, channel = "Joined", after.channel
        elif before.channel and not after.channel:
            action, channel = "Left", before.channel
        else:
            action, channel = "Moved", after.channel

        fields = [
            ("User", f"{member.mention} (`{member}`)", False),
            ("Channel", channel.mention, True),
        ]
        if action == "Moved":
            fields.append(("From", before.channel.mention, True))

        await self.send_log(
            member.guild, colour=COLOURS["voice"], title=f"🔊 Voice {action}", fields=fields
        )

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User | discord.Member):
        if user.bot or not reaction.message.guild:
            return
        await self.send_log(
            reaction.message.guild,
            colour=COLOURS["reaction"],
            title="➕ Reaction Added",
            fields=[
                ("User", f"{user.mention} (`{user}`)", False),
                ("Emoji", str(reaction.emoji), True),
                ("Message", f"[Jump]({reaction.message.jump_url})", True),
            ],
        )

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User | discord.Member):
        if user.bot or not reaction.message.guild:
            return
        await self.send_log(
            reaction.message.guild,
            colour=COLOURS["reaction"],
            title="➖ Reaction Removed",
            fields=[
                ("User", f"{user.mention} (`{user}`)", False),
                ("Emoji", str(reaction.emoji), True),
                ("Message", f"[Jump]({reaction.message.jump_url})", True),
            ],
        )

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        await self.send_log(
            channel.guild, colour=COLOURS["channel"], title="📢 Channel Created",
            fields=[("Name", channel.name, True), ("Type", str(channel.type), True), ("ID", str(channel.id), True)],
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        await self.send_log(
            channel.guild, colour=COLOURS["delete"], title="🗑️ Channel Deleted",
            fields=[("Name", channel.name, True), ("Type", str(channel.type), True), ("ID", str(channel.id), True)],
        )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        await self.send_log(
            role.guild, colour=COLOURS["role"], title="✨ Role Created",
            fields=[("Name", role.name, True), ("ID", str(role.id), True), ("Colour", str(role.colour), True)],
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        await self.send_log(
            role.guild, colour=COLOURS["delete"], title="🗑️ Role Deleted",
            fields=[("Name", role.name, True), ("ID", str(role.id), True)],
        )

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        if not ctx.guild:
            return
        await self.send_log(
            ctx.guild, colour=COLOURS["command"], title="⌨️ Prefix Command Used",
            fields=[
                ("User", f"{ctx.author.mention} (`{ctx.author}`)", False),
                ("Command", f"`{ctx.message.content}`", False),
                ("Channel", ctx.channel.mention, True),
            ],
        )

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound) or not ctx.guild:
            return
        await self.send_log(
            ctx.guild, colour=COLOURS["error"], title="❌ Command Error",
            fields=[
                ("User", f"{ctx.author.mention} (`{ctx.author}`)", False),
                ("Command", f"`{ctx.message.content}`", False),
                ("Error", str(error), False),
            ],
        )

    @app_commands.command(name="setlogchannel", description="Set the channel where logs are sent")
    @has_any_role(OWNER_ROLE_ID)
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        global _log_channel_id
        _log_channel_id = channel.id
        self._log_channel = channel
        await interaction.response.send_message(
            f"✅ Log channel set to {channel.mention}", ephemeral=True
        )

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have the required role.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Logging(bot))