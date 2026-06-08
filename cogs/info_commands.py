"""
Adds two slash commands to post server info as embeds:
  /post-rules — Posts the server rules embed
  /post-roles — Posts the server roles embed
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

from config import has_any_role, HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID


class InfoCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="post-rules", description="Post the server rules embed in this channel")
    @has_any_role(HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
    async def post_rules(self, interaction: discord.Interaction):
        guild = interaction.guild

        embed = discord.Embed(
            title="📋 Server Rules",
            description=(
                "By being in this server you agree to everything in this channel.\n\n"
                "You understand that Staff have the right to remove or punish you at any time without reason. "
                "If you wish to appeal, you can do so in the appeals channel *(if you have been warned or muted)*.\n\n"
                "Being in this server isn't a right, it's a privilege. "
                "If you wish to report a member or staff member, do so in <#1117369321040138260>.\n\n"
                "These rules may be updated at any time — it is your responsibility to stay up to date."
            ),
            colour=0xE74C3C,
            timestamp=datetime.now(timezone.utc),
        )

        rules = [
            ("Rule 1 — Be Respectful", "You must be respectful of all users regardless of your feelings towards them. Treat others how you want to be treated."),
            ("Rule 2 — No NSFW", "Any NSFW content will result in an **immediate ban with no appeal**."),
            ("Rule 3 — No Spamming", "Don't send lots of small messages right after each other. Do not disrupt chat via spamming. The one place you can spam is <#1117364519988109312>."),
            ("Rule 4 — No Advertisements", "We do not tolerate any kind of advertisements, whether for other communities or streams. You can post your content in the media channel."),
            ("Rule 5 — No Offensive Names or Profile Pictures", "If a staff member deems your nickname or profile picture inappropriate, you will be given a chance to change it before action is taken."),
            ("Rule 6 — No Server Raiding", "Raiding or mentions of raiding are not tolerated and action will be taken."),
            ("Rule 7 — No Threats", "Threats to other users are absolutely prohibited."),
            ("Rule 8 — Final Word", "The staff member always has the final word. Staff members will always have the @STAFF role."),
            ("Rule 9 — Keep Channels On-Topic", "Keep channels for their intended topic. No bot commands in general chat, no off-topic chat in dedicated channels."),
            ("Rule 10 — DMs", "Don't DM someone unless they've said it's okay. Never DM a @STAFF member unless it's an emergency — contact staff in <#1117369321040138260> instead."),
            ("Rule 11 — No Cold Pinging", "Do not cold ping — it will result in a warning."),
            ("Rule 12 — Age Requirement", "You must be at least 13 years old as per Discord's ToS. If we deem anyone to be under this age, you will be put on hold while we contact Discord."),
            ("Rule 13 — Discord ToS & Guidelines", "Follow Discord's Terms of Service and Community Guidelines.\n[Terms of Service](https://discord.com/terms) • [Guidelines](https://discordapp.com/guidelines)"),
        ]

        for name, value in rules:
            embed.add_field(name=name, value=value, inline=False)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"{guild.name} • Last updated")

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Rules posted.", ephemeral=True)

    @app_commands.command(name="post-roles", description="Post the server roles embed in this channel")
    @has_any_role(HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
    async def post_roles(self, interaction: discord.Interaction):
        guild = interaction.guild

        embed = discord.Embed(
            title="🏷️ Server Roles",
            description="A breakdown of all roles in the server. Most obtainable roles can be selected in the roles channel!",
            colour=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )

        embed.add_field(
            name="👮 Staff Roles",
            value=(
                "👑 **OllieOatMeal** — The server owner.\n"
                "🔴 **Head Admin** — Head of the staff team, hand-picked by the owner.\n"
                "🟠 **Admin** — Staff member who passed the trainee course.\n"
                "🟡 **Trainee** — Passed the staff application and currently on trial.\n"
                "🟢 **Staff** — A member of the staff team."
            ),
            inline=False,
        )

        embed.add_field(
            name="👥 Member Roles",
            value=(
                "✅ **Member** — Standard role received after agreeing to the rules.\n"
                "🎥 **Content Creator** — YouTube channel with 500+ subscribers. Apply via ticket.\n"
                "🤝 **Helper** — Helped the community significantly. Hand-picked by Head Admin & Owner.\n"
                "💜 **Supporter** — Boosted the server or contributed massively. Unlocks private channels.\n"
                "👋 **Friend** — Knows OllieOatMeal in real life."
            ),
            inline=False,
        )

        embed.add_field(
            name="🎨 Colour Roles",
            value="🔴 Red  •  🟠 Orange  •  🟡 Yellow  •  🟢 Green  •  🔵 Blue  •  🟣 Purple",
            inline=False,
        )

        embed.add_field(
            name="⭐ Level Roles",
            value=(
                "**Level 1** — Welcome to the server!\n"
                "**Level 5** — Video in VCs + embed links.\n"
                "**Level 10** — Attach files + use activities.\n"
                "**Level 25** — External emojis & stickers.\n"
                "**Level 50** — Add reactions.\n"
                "**Level 100** — Internal/external soundboards + priority speaker."
            ),
            inline=False,
        )

        embed.add_field(
            name="🔔 Ping Roles",
            value=(
                "**QOTD** — Notified for new Questions of the Day.\n"
                "**Announcement** — Pinged for new announcements.\n"
                "**New Emoji** — Pinged when a new emoji or sticker is added.\n"
                "**Updates** — Pinged for Discord server updates."
            ),
            inline=False,
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=guild.name)

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Roles posted.", ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have the required role.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(InfoCommands(bot))