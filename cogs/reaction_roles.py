# ══════════════════════════════════════════════════════════════════════════════
# cogs/reaction_roles.py — Reaction role system
# ══════════════════════════════════════════════════════════════════════════════
#
# Commands (Moderator or Admin only):
#   /reactionrole add    — Attach a reaction role to an existing message
#   /reactionrole create — Create a new embed and attach a reaction role to it
#   /reactionrole remove — Remove a reaction role entry
#   /reactionrole list   — List all active reaction roles in this server

import discord
from discord.ext import commands
from discord import app_commands
from config import has_any_role, OWNER_ROLE_ID

# reaction_roles_db[guild_id][(message_id, emoji_str)] = role_id
RRKey = tuple[int, str]
reaction_roles_db: dict[int, dict[RRKey, int]] = {}


class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_db(self, guild_id: int) -> dict[RRKey, int]:
        if guild_id not in reaction_roles_db:
            reaction_roles_db[guild_id] = {}
        return reaction_roles_db[guild_id]

    rr_group = app_commands.Group(name="reactionrole", description="Manage reaction roles")

    # ── /reactionrole add ─────────────────────────────────────────────────────
    @rr_group.command(name="add", description="Attach a reaction role to an existing message")
    @app_commands.describe(
        channel="The channel containing the message",
        message_id="ID of the message",
        emoji="Emoji to react with",
        role="Role to assign",
    )
    @has_any_role(OWNER_ROLE_ID)
    async def rr_add(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message_id: str,
        emoji: str,
        role: discord.Role,
    ):
        try:
            mid = int(message_id)
            message = await channel.fetch_message(mid)
        except (ValueError, discord.NotFound):
            return await interaction.response.send_message("❌ Message not found.", ephemeral=True)

        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                "❌ That role is above my highest role — I can't assign it.", ephemeral=True
            )

        db = self._get_db(interaction.guild.id)
        db[(mid, emoji)] = role.id

        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            return await interaction.response.send_message(
                "❌ Could not add that reaction. Make sure the emoji is valid.", ephemeral=True
            )

        await interaction.response.send_message(
            f"✅ Reacting with {emoji} on [that message]({message.jump_url}) will grant {role.mention}.",
            ephemeral=True,
        )

    # ── /reactionrole create ──────────────────────────────────────────────────
    @rr_group.command(name="create", description="Create a new embed and attach a reaction role to it")
    @app_commands.describe(
        channel="Channel to post the embed in",
        title="Embed title",
        description="Embed description",
        emoji="Emoji to react with",
        role="Role to assign when user reacts",
        colour="Hex colour for the embed (e.g. ff5733)",
    )
    @has_any_role(OWNER_ROLE_ID)
    async def rr_create(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        description: str,
        emoji: str,
        role: discord.Role,
        colour: str = "7289da",
    ):
        if role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                "❌ That role is above my highest role — I can't assign it.", ephemeral=True
            )
        try:
            colour_int = int(colour.lstrip("#"), 16)
        except ValueError:
            colour_int = 0x7289DA

        embed = discord.Embed(title=title, description=description, colour=colour_int)
        embed.set_footer(text=f"React with {emoji} to get the {role.name} role")
        message = await channel.send(embed=embed)

        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            await message.delete()
            return await interaction.response.send_message("❌ Invalid emoji. Message was not posted.", ephemeral=True)

        db = self._get_db(interaction.guild.id)
        db[(message.id, emoji)] = role.id

        await interaction.response.send_message(
            f"✅ Created reaction role embed in {channel.mention}.", ephemeral=True
        )

    # ── /reactionrole remove ──────────────────────────────────────────────────
    @rr_group.command(name="remove", description="Remove a reaction role entry")
    @app_commands.describe(message_id="ID of the message", emoji="Emoji of the reaction role to remove")
    @has_any_role(OWNER_ROLE_ID)
    async def rr_remove(self, interaction: discord.Interaction, message_id: str, emoji: str):
        try:
            mid = int(message_id)
        except ValueError:
            return await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)

        db = self._get_db(interaction.guild.id)
        key = (mid, emoji)
        if key not in db:
            return await interaction.response.send_message(
                "❌ No reaction role found for that message/emoji combo.", ephemeral=True
            )
        del db[key]
        await interaction.response.send_message("✅ Reaction role removed.", ephemeral=True)

    # ── /reactionrole list ────────────────────────────────────────────────────
    @rr_group.command(name="list", description="List all active reaction roles in this server")
    @has_any_role(OWNER_ROLE_ID)
    async def rr_list(self, interaction: discord.Interaction):
        db = self._get_db(interaction.guild.id)
        if not db:
            return await interaction.response.send_message("No reaction roles set up yet.", ephemeral=True)

        embed = discord.Embed(title="🎭 Reaction Roles", colour=0x9B59B6)
        for (message_id, emoji), role_id in db.items():
            role = interaction.guild.get_role(role_id)
            embed.add_field(
                name=f"{emoji} → {role.name if role else f'Unknown ({role_id})'}",
                value=f"Message ID: `{message_id}`",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Listeners ─────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id or not payload.guild_id:
            return
        db = self._get_db(payload.guild_id)
        role_id = db.get((payload.message_id, str(payload.emoji)))
        if not role_id:
            return
        guild  = self.bot.get_guild(payload.guild_id)
        role   = guild.get_role(role_id)
        member = guild.get_member(payload.user_id)
        if role and member:
            try:
                await member.add_roles(role, reason="Reaction role")
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id or not payload.guild_id:
            return
        db = self._get_db(payload.guild_id)
        role_id = db.get((payload.message_id, str(payload.emoji)))
        if not role_id:
            return
        guild  = self.bot.get_guild(payload.guild_id)
        role   = guild.get_role(role_id)
        member = guild.get_member(payload.user_id)
        if role and member:
            try:
                await member.remove_roles(role, reason="Reaction role removed")
            except discord.Forbidden:
                pass

    # ── Error handler ─────────────────────────────────────────────────────────
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have the required role.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))