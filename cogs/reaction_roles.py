# ══════════════════════════════════════════════════════════════════════════════
# cogs/reaction_roles.py — Reaction role system
# ══════════════════════════════════════════════════════════════════════════════
#
# Each emoji on a message can:
#   • ADD   any number of roles when a user reacts
#   • REMOVE any number of roles when a user reacts
#
# Data persists in data/reaction_roles.json across restarts.
#
# Commands (Owner only):
#   /reactionrole add     — Attach an emoji to a message; set roles to add/remove
#   /reactionrole create  — Create a new embed and attach an emoji to it
#   /reactionrole remove  — Remove one emoji entry from a message
#   /reactionrole edit    — Add or remove roles from an existing emoji entry
#   /reactionrole list    — List all active reaction roles in this server
# ══════════════════════════════════════════════════════════════════════════════

import json
import os

"""
cogs/reaction_roles.py
───────────────────────
Self-assignable roles delivered via button panels.
Configuration is persisted to data/reaction_roles.json.

Commands (Owner required):
  /rr create  — Create a new reaction-role panel in a channel
  /rr add     — Add a role+emoji button to an existing panel
  /rr remove  — Remove a role from a panel
  /rr delete  — Delete an entire panel

Users click buttons on the panel to toggle their roles.
"""

import discord
from discord import app_commands
from discord.ext import commands

from config import has_any_role, OWNER_ROLE_ID

# ── Persistent storage ────────────────────────────────────────────────────────
# Schema: { guild_id: { message_id: { emoji: { "add": [role_id,...], "remove": [role_id,...] } } } }

DATA_DIR = "data"
RR_FILE  = os.path.join(DATA_DIR, "reaction_roles.json")
os.makedirs(DATA_DIR, exist_ok=True)


def _load() -> dict:
    try:
        with open(RR_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict):
    with open(RR_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _get_entry(data: dict, guild_id: int, message_id: int, emoji: str) -> dict | None:
    return data.get(str(guild_id), {}).get(str(message_id), {}).get(emoji)


def _set_entry(data: dict, guild_id: int, message_id: int, emoji: str, entry: dict):
    g = str(guild_id)
    m = str(message_id)
    data.setdefault(g, {}).setdefault(m, {})[emoji] = entry
    _save(data)


def _del_entry(data: dict, guild_id: int, message_id: int, emoji: str):
    g, m = str(guild_id), str(message_id)
    data.get(g, {}).get(m, {}).pop(emoji, None)
    # Clean up empty dicts
    if not data.get(g, {}).get(m):
        data.get(g, {}).pop(m, None)
    if not data.get(g):
        data.pop(g, None)
    _save(data)


def _parse_role_ids(raw: str) -> list[int]:
    """Parse a comma-separated string of role IDs/mentions into a list of ints."""
    ids = []
    for part in raw.replace("<@&", "").replace(">", "").split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


# ── Cog ───────────────────────────────────────────────────────────────────────

class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    rr_group = app_commands.Group(name="reactionrole", description="Manage reaction roles")

    # ── /reactionrole add ─────────────────────────────────────────────────────

    @rr_group.command(name="add", description="Attach a reaction role to an existing message")
    @app_commands.describe(
        channel="The channel containing the message",
        message_id="ID of the message",
        emoji="Emoji to react with",
        roles_to_add="Roles to ADD when reacted (comma-separated IDs or mentions, leave blank for none)",
        roles_to_remove="Roles to REMOVE when reacted (comma-separated IDs or mentions, leave blank for none)",
    )
    @has_any_role(OWNER_ROLE_ID)
    async def rr_add(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message_id: str,
        emoji: str,
        roles_to_add: str = "",
        roles_to_remove: str = "",
    ):
        try:
            mid = int(message_id)
            message = await channel.fetch_message(mid)
        except (ValueError, discord.NotFound):
            return await interaction.response.send_message("❌ Message not found.", ephemeral=True)

        add_ids    = _parse_role_ids(roles_to_add)
        remove_ids = _parse_role_ids(roles_to_remove)

        if not add_ids and not remove_ids:
            return await interaction.response.send_message(
                "❌ You must specify at least one role to add or remove.", ephemeral=True
            )

        # Validate all roles are below the bot's top role
        all_ids = add_ids + remove_ids
        for rid in all_ids:
            role = interaction.guild.get_role(rid)
            if role and role >= interaction.guild.me.top_role:
                return await interaction.response.send_message(
                    f"❌ {role.mention} is above my highest role — I can't manage it.", ephemeral=True
                )

        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            return await interaction.response.send_message(
                "❌ Could not add that reaction. Make sure the emoji is valid.", ephemeral=True
            )

        data = _load()
        _set_entry(data, interaction.guild.id, mid, emoji, {"add": add_ids, "remove": remove_ids})

        add_mentions    = " ".join(f"<@&{r}>" for r in add_ids)    or "None"
        remove_mentions = " ".join(f"<@&{r}>" for r in remove_ids) or "None"

        embed = discord.Embed(
            title="✅ Reaction Role Set",
            description=f"[Jump to message]({message.jump_url})",
            colour=0x2ECC71,
        )
        embed.add_field(name="Emoji",        value=emoji,          inline=True)
        embed.add_field(name="Adds roles",   value=add_mentions,   inline=False)
        embed.add_field(name="Removes roles",value=remove_mentions,inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /reactionrole create ──────────────────────────────────────────────────

    @rr_group.command(name="create", description="Create a new embed and attach a reaction role to it")
    @app_commands.describe(
        channel="Channel to post the embed in",
        title="Embed title",
        description="Embed description",
        emoji="Emoji to react with",
        roles_to_add="Roles to ADD when reacted (comma-separated IDs or mentions)",
        roles_to_remove="Roles to REMOVE when reacted (comma-separated IDs or mentions, leave blank for none)",
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
        roles_to_add: str = "",
        roles_to_remove: str = "",
        colour: str = "7289da",
    ):
        add_ids    = _parse_role_ids(roles_to_add)
        remove_ids = _parse_role_ids(roles_to_remove)

        if not add_ids and not remove_ids:
            return await interaction.response.send_message(
                "❌ You must specify at least one role to add or remove.", ephemeral=True
            )

        for rid in add_ids + remove_ids:
            role = interaction.guild.get_role(rid)
            if role and role >= interaction.guild.me.top_role:
                return await interaction.response.send_message(
                    f"❌ {role.mention} is above my highest role.", ephemeral=True
                )

        try:
            colour_int = int(colour.lstrip("#"), 16)
        except ValueError:
            colour_int = 0x7289DA

        # Build footer listing the roles
        add_names    = ", ".join(interaction.guild.get_role(r).name for r in add_ids    if interaction.guild.get_role(r)) or "None"
        remove_names = ", ".join(interaction.guild.get_role(r).name for r in remove_ids if interaction.guild.get_role(r)) or "None"
        footer = f"React with {emoji}"
        if add_ids:    footer += f" to gain: {add_names}"
        if remove_ids: footer += f" | to lose: {remove_names}"

        embed = discord.Embed(title=title, description=description, colour=colour_int)
        embed.set_footer(text=footer)
        message = await channel.send(embed=embed)

        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            await message.delete()
            return await interaction.response.send_message("❌ Invalid emoji. Message was not posted.", ephemeral=True)

        data = _load()
        _set_entry(data, interaction.guild.id, message.id, emoji, {"add": add_ids, "remove": remove_ids})

        await interaction.response.send_message(
            f"✅ Reaction role embed posted in {channel.mention}.", ephemeral=True
        )

    # ── /reactionrole edit ────────────────────────────────────────────────────

    @rr_group.command(name="edit", description="Add or remove roles from an existing reaction role entry")
    @app_commands.describe(
        message_id="ID of the message",
        emoji="Emoji of the existing entry",
        add_to_add="Extra role IDs/mentions to add to the 'add' list",
        remove_from_add="Role IDs/mentions to remove from the 'add' list",
        add_to_remove="Extra role IDs/mentions to add to the 'remove' list",
        remove_from_remove="Role IDs/mentions to remove from the 'remove' list",
    )
    @has_any_role(OWNER_ROLE_ID)
    async def rr_edit(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        add_to_add: str = "",
        remove_from_add: str = "",
        add_to_remove: str = "",
        remove_from_remove: str = "",
    ):
        try:
            mid = int(message_id)
        except ValueError:
            return await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)

        data  = _load()
        entry = _get_entry(data, interaction.guild.id, mid, emoji)
        if not entry:
            return await interaction.response.send_message(
                "❌ No reaction role found for that message/emoji.", ephemeral=True
            )

        current_add    = set(entry.get("add", []))
        current_remove = set(entry.get("remove", []))

        current_add    |= set(_parse_role_ids(add_to_add))
        current_add    -= set(_parse_role_ids(remove_from_add))
        current_remove |= set(_parse_role_ids(add_to_remove))
        current_remove -= set(_parse_role_ids(remove_from_remove))

        entry = {"add": list(current_add), "remove": list(current_remove)}
        _set_entry(data, interaction.guild.id, mid, emoji, entry)

        add_mentions    = " ".join(f"<@&{r}>" for r in current_add)    or "None"
        remove_mentions = " ".join(f"<@&{r}>" for r in current_remove) or "None"

        embed = discord.Embed(title="✅ Reaction Role Updated", colour=0x2ECC71)
        embed.add_field(name="Emoji",         value=emoji,          inline=True)
        embed.add_field(name="Now adds",      value=add_mentions,   inline=False)
        embed.add_field(name="Now removes",   value=remove_mentions,inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /reactionrole remove ──────────────────────────────────────────────────

    @rr_group.command(name="remove", description="Remove a reaction role entry entirely")
    @app_commands.describe(message_id="ID of the message", emoji="Emoji of the reaction role to remove")
    @has_any_role(OWNER_ROLE_ID)
    async def rr_remove(self, interaction: discord.Interaction, message_id: str, emoji: str):
        try:
            mid = int(message_id)
        except ValueError:
            return await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)

        data  = _load()
        entry = _get_entry(data, interaction.guild.id, mid, emoji)
        if not entry:
            return await interaction.response.send_message(
                "❌ No reaction role found for that message/emoji combo.", ephemeral=True
            )

        _del_entry(data, interaction.guild.id, mid, emoji)
        await interaction.response.send_message(
            f"✅ Reaction role ({emoji}) removed from message `{mid}`.", ephemeral=True
        )

    # ── /reactionrole list ────────────────────────────────────────────────────

    @rr_group.command(name="list", description="List all active reaction roles in this server")
    @has_any_role(OWNER_ROLE_ID)
    async def rr_list(self, interaction: discord.Interaction):
        data    = _load()
        guild_data = data.get(str(interaction.guild.id), {})

        if not guild_data:
            return await interaction.response.send_message("No reaction roles set up yet.", ephemeral=True)

        embed = discord.Embed(title="🎭 Reaction Roles", colour=0x9B59B6)
        for message_id, emojis in guild_data.items():
            for emoji, entry in emojis.items():
                add_names    = " ".join(f"<@&{r}>" for r in entry.get("add", []))    or "None"
                remove_names = " ".join(f"<@&{r}>" for r in entry.get("remove", [])) or "None"
                embed.add_field(
                    name=f"{emoji}  —  Message `{message_id}`",
                    value=f"**Adds:** {add_names}\n**Removes:** {remove_names}",
                    inline=False,
                )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Listeners ─────────────────────────────────────────────────────────────

    async def _apply(self, payload: discord.RawReactionActionEvent, reacting: bool):
        """reacting=True means adding reaction, False means removing it."""
        if payload.user_id == self.bot.user.id or not payload.guild_id:
            return

        data  = _load()
        entry = _get_entry(data, payload.guild_id, payload.message_id, str(payload.emoji))
        if not entry:
            return

        guild  = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if not member:
            return

        # When reacting: add the "add" roles and remove the "remove" roles
        # When un-reacting: reverse — remove the "add" roles and add the "remove" roles
        roles_to_grant = entry.get("add", [])    if reacting else entry.get("remove", [])
        roles_to_revoke= entry.get("remove", []) if reacting else entry.get("add", [])

        for rid in roles_to_grant:
            role = guild.get_role(rid)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Reaction role")
                except discord.Forbidden:
                    pass

        for rid in roles_to_revoke:
            role = guild.get_role(rid)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Reaction role")
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self._apply(payload, reacting=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._apply(payload, reacting=False)

    # ── Error handler ─────────────────────────────────────────────────────────

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have the required role.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))
    print("ReactionRoles cog loaded")