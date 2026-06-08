"""
cogs/embeds.py
───────────────
Slash commands for creating and managing Discord embeds.

Commands (Head Admin+ required for all):
  /embed simple   — Quick one-line embed creation
  /embed builder  — Interactive modal-based embed builder
  /embed announce — Pre-styled announcement embed with optional role ping
  /embed rules    — Post a numbered rules embed
  /embed edit     — Edit an embed the bot has already sent
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from config import has_any_role, HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID


def parse_colour(colour_str: str) -> int:
    try:
        return int(colour_str.lstrip("#"), 16)
    except (ValueError, AttributeError):
        return 0x7289DA


class EmbedBuilderModal(discord.ui.Modal, title="Embed Builder"):
    embed_title = discord.ui.TextInput(label="Title", placeholder="Your embed title...", max_length=256)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Main body text...", max_length=4000)
    colour      = discord.ui.TextInput(label="Colour (hex, e.g. ff5733)", placeholder="7289da", max_length=7, required=False, default="7289da")
    footer      = discord.ui.TextInput(label="Footer text", placeholder="Optional footer...", max_length=2048, required=False)
    image_url   = discord.ui.TextInput(label="Image URL (optional)", placeholder="https://example.com/image.png", required=False)

    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=self.embed_title.value,
            description=self.description.value,
            colour=parse_colour(self.colour.value or "7289da"),
            timestamp=datetime.now(timezone.utc),
        )
        if self.footer.value:
            embed.set_footer(text=self.footer.value)
        if self.image_url.value:
            embed.set_image(url=self.image_url.value)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        await self.channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Embed sent to {self.channel.mention}!", ephemeral=True)


class EmbedEditModal(discord.ui.Modal, title="Edit Embed"):
    new_title       = discord.ui.TextInput(label="New Title", max_length=256, required=False)
    new_description = discord.ui.TextInput(label="New Description", style=discord.TextStyle.paragraph, max_length=4000, required=False)
    new_colour      = discord.ui.TextInput(label="New Colour (hex)", max_length=7, required=False)
    new_footer      = discord.ui.TextInput(label="New Footer", max_length=2048, required=False)

    def __init__(self, message: discord.Message):
        super().__init__()
        self.message = message
        existing = message.embeds[0] if message.embeds else None
        if existing:
            if existing.title:       self.new_title.default       = existing.title
            if existing.description: self.new_description.default = existing.description
            if existing.footer and existing.footer.text:
                self.new_footer.default = existing.footer.text

    async def on_submit(self, interaction: discord.Interaction):
        existing    = self.message.embeds[0] if self.message.embeds else discord.Embed()
        title       = self.new_title.value       or existing.title
        description = self.new_description.value or existing.description
        colour      = parse_colour(self.new_colour.value) if self.new_colour.value else existing.colour.value
        footer_text = self.new_footer.value or (existing.footer.text if existing.footer else None)

        new_embed = discord.Embed(title=title, description=description, colour=colour, timestamp=existing.timestamp)
        if footer_text:
            new_embed.set_footer(text=footer_text)
        if existing.author and existing.author.name:
            new_embed.set_author(name=existing.author.name, icon_url=existing.author.icon_url)
        if existing.image and existing.image.url:
            new_embed.set_image(url=existing.image.url)
        if existing.thumbnail and existing.thumbnail.url:
            new_embed.set_thumbnail(url=existing.thumbnail.url)

        await self.message.edit(embed=new_embed)
        await interaction.response.send_message("✅ Embed updated!", ephemeral=True)


class Embeds(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    embed_group = app_commands.Group(name="embed", description="Create and manage embeds")

    @embed_group.command(name="simple", description="Send a simple embed quickly")
    @app_commands.describe(
        channel="Channel to send the embed to", title="Embed title", description="Embed description",
        colour="Hex colour (e.g. ff5733)", footer="Optional footer text",
        thumbnail="Optional thumbnail URL", image="Optional image URL",
        ping_role="Optional role to ping alongside the embed",
    )
    @has_any_role(HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
    async def embed_simple(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        description: str,
        colour: str = "7289da",
        footer: str = None,
        thumbnail: str = None,
        image: str = None,
        ping_role: discord.Role = None,
    ):
        embed = discord.Embed(title=title, description=description, colour=parse_colour(colour), timestamp=datetime.now(timezone.utc))
        if footer:    embed.set_footer(text=footer)
        if thumbnail: embed.set_thumbnail(url=thumbnail)
        if image:     embed.set_image(url=image)
        await channel.send(content=ping_role.mention if ping_role else None, embed=embed)
        await interaction.response.send_message(f"✅ Embed sent to {channel.mention}!", ephemeral=True)

    @embed_group.command(name="builder", description="Open an interactive embed builder")
    @app_commands.describe(channel="Channel to send the finished embed to")
    @has_any_role(HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
    async def embed_builder(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.send_modal(EmbedBuilderModal(channel))

    @embed_group.command(name="announce", description="Send a pre-styled announcement embed")
    @app_commands.describe(channel="Channel to announce in", title="Announcement title", message="Announcement body", ping_role="Role to ping (optional)")
    @has_any_role(HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
    async def embed_announce(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        message: str,
        ping_role: discord.Role = None,
    ):
        embed = discord.Embed(title=f"📢 {title}", description=message, colour=0xE91E63, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Announcement by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        if interaction.guild.icon:
            embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await channel.send(content=ping_role.mention if ping_role else None, embed=embed)
        await interaction.response.send_message(f"✅ Announcement sent to {channel.mention}!", ephemeral=True)

    @embed_group.command(name="rules", description="Post a rules embed with numbered rules")
    @app_commands.describe(
        channel="Channel to post rules in", title="Rules title",
        rules="Rules separated by | (e.g. Be respectful|No spam|No NSFW)",
        footer="Optional footer text",
    )
    @has_any_role(HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
    async def embed_rules(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str = "📜 Server Rules",
        rules: str = "",
        footer: str = "By participating in this server, you agree to these rules.",
    ):
        rule_list = [r.strip() for r in rules.split("|") if r.strip()]
        if not rule_list:
            return await interaction.response.send_message("❌ Provide at least one rule, separated by `|`.", ephemeral=True)

        embed = discord.Embed(
            title=title,
            description="\n".join(f"**{i}.** {rule}" for i, rule in enumerate(rule_list, 1)),
            colour=0x2ECC71,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=footer)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        await channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Rules posted in {channel.mention}!", ephemeral=True)

    @embed_group.command(name="edit", description="Edit an existing embed sent by this bot")
    @app_commands.describe(channel="Channel containing the message", message_id="ID of the message to edit")
    @has_any_role(HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
    async def embed_edit(self, interaction: discord.Interaction, channel: discord.TextChannel, message_id: str):
        try:
            mid     = int(message_id)
            message = await channel.fetch_message(mid)
        except (ValueError, discord.NotFound):
            return await interaction.response.send_message("❌ Message not found.", ephemeral=True)

        if message.author != interaction.guild.me:
            return await interaction.response.send_message("❌ I can only edit embeds that I sent.", ephemeral=True)
        if not message.embeds:
            return await interaction.response.send_message("❌ That message has no embed to edit.", ephemeral=True)

        await interaction.response.send_modal(EmbedEditModal(message))

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have the required role.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Embeds(bot))