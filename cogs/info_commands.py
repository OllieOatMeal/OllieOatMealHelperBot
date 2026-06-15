"""
Adds two slash commands to post server info as embeds:
  /post-rules — Posts the server rules embed
  /post-roles — Posts the server roles embed
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

from config import has_any_role, CMD, PERMS


class InfoCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name=CMD["post_rules"], description="Post the server rules embed in this channel")
    @has_any_role(*PERMS["post_rules"])
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

    @app_commands.command(name=CMD["post_roles"], description="Post the server roles embed in this channel")
    @has_any_role(*PERMS["post_roles"])
    async def post_roles(self, interaction: discord.Interaction):
        guild = interaction.guild

        embed = discord.Embed(
            title="🏷️ Server Roles",
            description="A breakdown of all roles in the server. Most obtainable roles can be selected in the roles channel!",
            colour=0xE74C3C,
            timestamp=datetime.now(timezone.utc),
        )

        embed.add_field(
            name="👮 Staff Roles",
            value=(
                "**<@&1117190277522804826>** — The server owner.\n"
                "**<@&1117190624853110925>** — Head of the staff team, hand-picked by the owner.\n"
                "**<@&1117190992316076082>** — Staff member who passed the trainee course.\n"
                "**<@&1117191230485438584>** — Passed the staff application and currently on trial.\n"
                "**<@&1117193288051601508>** — A member of the staff team."
            ),
            inline=False,
        )

        embed.add_field(
            name="👥 Member Roles",
            value=(
                "**<@&1117193057918533662>** — Standard role received after agreeing to the rules.\n"
                "**<@&1117387942592270367>** — YouTube channel with 500+ subscribers. Apply via ticket.\n"
                "**<@&1117196806309298246>** — Helped the community significantly. Hand-picked by Head Admin & Owner.\n"
                "**<@&1117192871888556134>** — Boosted the server or contributed massively. Unlocks private channels.\n"
                "**<@&1117351974988419163>** — Knows OllieOatMeal in real life."
            ),
            inline=False,
        )

        embed.add_field(
            name="🎨 Colour Roles",
            value="<@&1117192362100260874>  •  <@&1117192408694792282>  •  <@&1117192494132768870>  •  <@&1117192530912612542>  •  <@&1117192570318106687>  •  <@&1117192599430766642>",
            inline=False,
        )

        embed.add_field(
            name="⭐ Level Roles",
            value=(
                "**<@&1117194084092760134>** — Welcome to the server!\n"
                "**<@&1117194409453293682>** — Video in VCs + embed links.\n"
                "**<@&1117194557554167900>** — Attach files + use activities.\n"
                "**<@&1117194754493526156>** — External emojis & stickers.\n"
                "**<@&1117195060551876741>** — Add reactions.\n"
                "**<@&1117195277036695635>** — Internal/external soundboards + priority speaker."
            ),
            inline=False,
        )

        embed.add_field(
            name="🔔 Ping Roles",
            value=(
                "**<@&1117197840444313600>** — Notified for new Questions of the Day.\n"
                "**<@&1117198075971252345>** — Pinged for new announcements.\n"
                "**<@&1117198815938760804>** — Pinged when a new emoji or sticker is added.\n"
                "**<@&1117198900319756318>** — Pinged for Discord server updates."
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