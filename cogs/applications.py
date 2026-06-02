# ══════════════════════════════════════════════════════════════════════════════
# cogs/applications.py — Application system with embeds and buttons
# ══════════════════════════════════════════════════════════════════════════════
#
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  CUSTOMISE YOUR APPLICATION FORMS HERE  (scroll to APPLICATIONS)    ║
# ╚══════════════════════════════════════════════════════════════════════╝
#
# HOW IT WORKS:
#   1. A moderator runs /application-panel to post a panel with one button
#      per application type you have defined.
#   2. Users click a button → a modal pops up with your questions.
#   3. Responses are posted as a rich embed to #mod-logs, with
#      Accept / Decline / On-Hold buttons for staff to action.
#   4. The applicant receives a DM with the outcome.
#
# HOW TO ADD / CHANGE QUESTIONS:
#   • Each application type is a dict in the APPLICATIONS list below.
#   • "questions" is a list of dicts, one per modal TextInput field.
#   • Max 5 questions per form (Discord modal limit).
#   • Set "style" to "short" (one line) or "paragraph" (multiline).

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from config import (
    has_any_role,
    ADMIN_ROLE_ID, STAFF_ROLE_ID,
    MEMBER_APPLICATION_LOG_CHANNEL_NAME, MEMBER_APPLICATION_PING_ROLE_ID, 
    STAFF_APPLICATION_LOG_CHANNEL_NAME, STAFF_APPLICATION_PING_ROLE_ID,
    MOD_LOG_CHANNEL_ID,
)

# ════════════════════════════════════════════════════════════════════════════
# ✏️  APPLICATIONS — Edit this list to add, remove, or change forms
# ════════════════════════════════════════════════════════════════════════════

MEMBER_APPLICATIONS: list[dict] = [
    {
        # ── Staff Application ─────────────────────────────────────────────
        "id":    "staff",           # Unique ID — do NOT change after deploying (used in custom_ids)
        "label": "Staff",           # Button label on the panel
        "emoji": "🛡️",             # Button emoji
        "colour": 0x5865F2,         # Embed accent colour (hex int)
        "questions": [
            {
                "label":       "What is your age?",
                "placeholder": "e.g. 18",
                "style":       "short",
                "required":    True,
                "max_length":  4,
            },
            {
                "label":       "What timezone are you in?",
                "placeholder": "e.g. GMT+1, EST, PST …",
                "style":       "short",
                "required":    True,
                "max_length":  30,
            },
            {
                "label":       "Why do you want to be staff?",
                "placeholder": "Tell us your motivation…",
                "style":       "paragraph",
                "required":    True,
                "max_length":  500,
            },
            {
                "label":       "Do you have prior moderation experience?",
                "placeholder": "Describe any relevant experience…",
                "style":       "paragraph",
                "required":    False,
                "max_length":  400,
            },
            {
                "label":       "Anything else you'd like us to know?",
                "placeholder": "Optional extra info…",
                "style":       "paragraph",
                "required":    False,
                "max_length":  300,
            },
        ],
    },
    {
        # ── Helper Application ────────────────────────────────────────────
        "id":    "helper",
        "label": "Helper",
        "emoji": "🤝",
        "colour": 0x2ECC71,
        "questions": [
            {
                "label":       "What is your age?",
                "placeholder": "e.g. 16",
                "style":       "short",
                "required":    True,
                "max_length":  4,
            },
            {
                "label":       "How active are you on the server?",
                "placeholder": "e.g. 3–4 hours a day",
                "style":       "short",
                "required":    True,
                "max_length":  100,
            },
            {
                "label":       "Why do you want to be a Helper?",
                "placeholder": "Explain your motivation…",
                "style":       "paragraph",
                "required":    True,
                "max_length":  500,
            },
        ],
    },
    {
        # ── Content Creator Application ─────────────────────────────────────
        "id":    "content_creator",
        "label": "Content Creator",
        "emoji": "🎥",
        "colour": 0xF39C12,
        "questions": [
            {
                "label":       "What content do you produce?",
                "placeholder": "e.g. tiktoks, youtube videos, streams...",
                "style":       "paragraph",
                "required":    True,
                "max_length":  300,
            },
            {
                "label":       "How often would you post?",
                "placeholder": "e.g. Once a week",
                "style":       "short",
                "required":    True,
                "max_length":  80,
            },
            {
                "label":       "Send a link to something you made which was received well...",
                "placeholder": "e.g. Tiktok or YouTube link",
                "style":       "short",
                "required":    True,
                "max_length":  100,
            },
        ],
    },
]
STAFF_APPLICATIONS: list[dict] = [
    {
        # ── Staff Promotion Application ─────────────────────────────────────
        "id":    "staff_promotion",
        "label": "Staff Promotion Application",
        "emoji": "🛡️",
        "colour": 0xF39C12,
        "questions": [
            {
                "label":       "Why should you be promoted?",
                "placeholder": "",
                "style":       "paragraph",
                "required":    True,
                "max_length":  400,
            },
            {
                "label":       "How active a week are you?",
                "placeholder": "e.g. 10 hours a week",
                "style":       "short",
                "required":    True,
                "max_length":  80,
            },
            {
                "label":       "What would you bring to the Senior Team?",
                "placeholder": "",
                "style":       "paragraph",
                "required":    True,
                "max_length":  400,
            },
        ],
    },
]

# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

def _get_app_config(app_id: str) -> dict | None:
    return next((a for a in MEMBER_APPLICATIONS if a["id"] == app_id), None)


async def _get_log_channel(guild: discord.Guild) -> discord.TextChannel | None:
    return discord.utils.get(guild.text_channels, name=MEMBER_APPLICATION_LOG_CHANNEL_NAME)

def _get_app_config(app_id: str) -> dict | None:
    return next((a for a in STAFF_APPLICATIONS if a["id"] == app_id), None)


async def _get_log_channel(guild: discord.Guild) -> discord.TextChannel | None:
    return discord.utils.get(guild.text_channels, name=STAFF_APPLICATION_LOG_CHANNEL_NAME)


# ════════════════════════════════════════════════════════════════════════════
# Dynamic Modal
# ════════════════════════════════════════════════════════════════════════════

def build_modal(app_config: dict, applicant: discord.Member) -> discord.ui.Modal:
    """Dynamically build a Modal from an application config dict."""

    class AppModal(discord.ui.Modal):
        def __init__(self):
            super().__init__(title=f"{app_config['label']} Application")
            self._app_config = app_config
            self._applicant = applicant
            for i, q in enumerate(app_config["questions"][:5]):
                style = discord.TextStyle.paragraph if q.get("style") == "paragraph" else discord.TextStyle.short
                item = discord.ui.TextInput(
                    label=q["label"],
                    placeholder=q.get("placeholder", ""),
                    style=style,
                    required=q.get("required", True),
                    max_length=q.get("max_length", 1024),
                    custom_id=f"q{i}",
                )
                self.add_item(item)

        async def on_submit(self, interaction: discord.Interaction):
            cfg = self._app_config
            answers = {item.label: item.value for item in self.children}

            # Build the result embed
            embed = discord.Embed(
                title=f"{cfg['emoji']} {cfg['label']} Application",
                colour=cfg["colour"],
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_author(
                name=str(self._applicant),
                icon_url=self._applicant.display_avatar.url,
            )
            embed.add_field(name="Applicant", value=f"{self._applicant.mention} (`{self._applicant.id}`)", inline=False)
            for question, answer in answers.items():
                embed.add_field(name=question, value=answer or "*No answer*", inline=False)
            embed.set_footer(text=f"User ID: {self._applicant.id}")

            log_ch = await _get_log_channel(interaction.guild)
            if not log_ch:
                await interaction.response.send_message(
                    "✅ Application submitted! Staff will review it shortly.", ephemeral=True
                )
                return

            # Ping role if configured
            ping_role = interaction.guild.get_role(MEMBER_APPLICATION_PING_ROLE_ID)
            ping_content = ping_role.mention if ping_role else ""

            app_msg = await log_ch.send(
                content=ping_content or None,
                embed=embed,
                view=ApplicationReviewView(
                    app_label=cfg["label"],
                    applicant=self._applicant,
                ),
            )

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="✅ Application Submitted",
                    description=(
                        f"Your **{cfg['label']}** application has been received!\n"
                        "You'll be notified when staff have reviewed it."
                    ),
                    colour=cfg["colour"],
                ),
                ephemeral=True,
            )

    return AppModal()


# ════════════════════════════════════════════════════════════════════════════
# Review View (posted in mod-logs with each application)
# ════════════════════════════════════════════════════════════════════════════

class ApplicationReviewView(discord.ui.View):
    """Accept / Decline / On-Hold buttons for staff."""

    def __init__(self, app_label: str, applicant: discord.Member):
        super().__init__(timeout=None)
        self.app_label = app_label
        self.applicant = applicant

    def _staff_only(self, interaction: discord.Interaction) -> bool:
        return any(r.id in (ADMIN_ROLE_ID, MODERATOR_ROLE_ID) for r in interaction.user.roles)

    async def _update(self, interaction: discord.Interaction, status: str, colour: int, dm_text: str):
        if not self._staff_only(interaction):
            return await interaction.response.send_message("❌ Only staff can review applications.", ephemeral=True)

        # Edit the embed to show the decision
        original_embed = interaction.message.embeds[0]
        updated = original_embed.copy()
        updated.colour = colour
        updated.add_field(
            name="Decision",
            value=f"{status} by {interaction.user.mention}",
            inline=False,
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=updated, view=self)

        # DM the applicant
        try:
            await self.applicant.send(
                embed=discord.Embed(
                    title=f"{self.app_label} Application — {status}",
                    description=dm_text,
                    colour=colour,
                    timestamp=datetime.now(timezone.utc),
                )
            )
        except discord.Forbidden:
            pass

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅", custom_id="app:accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update(
            interaction, "✅ Accepted", 0x2ECC71,
            f"🎉 Congratulations! Your **{self.app_label}** application has been **accepted**.\n"
            "A staff member will be in touch shortly."
        )

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌", custom_id="app:decline")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update(
            interaction, "❌ Declined", 0xE74C3C,
            f"Thank you for applying for **{self.app_label}**.\n"
            "Unfortunately, your application was **not successful** at this time.\n"
            "You're welcome to reapply in the future!"
        )

    @discord.ui.button(label="On Hold", style=discord.ButtonStyle.secondary, emoji="⏸️", custom_id="app:onhold")
    async def on_hold(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update(
            interaction, "⏸️ On Hold", 0xF39C12,
            f"Your **{self.app_label}** application has been placed **on hold**.\n"
            "Staff are still reviewing it — we'll get back to you soon."
        )


# ════════════════════════════════════════════════════════════════════════════
# Panel View
# ════════════════════════════════════════════════════════════════════════════

class MemberApplicationPanelView(discord.ui.View):
    """One button per application type. Posted by /application-panel."""

    def __init__(self):
        super().__init__(timeout=None)
        for app in MEMBER_APPLICATIONS:
            btn = discord.ui.Button(
                label=app["label"],
                emoji=app["emoji"],
                style=discord.ButtonStyle.primary,
                custom_id=f"app:open:{app['id']}",
            )
            btn.callback = self._make_callback(app["id"])
            self.add_item(btn)

    def _make_callback(self, app_id: str):
        async def callback(interaction: discord.Interaction):
            cfg = _get_app_config(app_id)
            if not cfg:
                return await interaction.response.send_message("❌ Application type not found.", ephemeral=True)
            modal = build_modal(cfg, interaction.user)
            await interaction.response.send_modal(modal)
        return callback

class StaffApplicationPanelView(discord.ui.View):
    """One button per application type. Posted by /application-panel."""

    def __init__(self):
        super().__init__(timeout=None)
        for app in MEMBER_APPLICATIONS:
            btn = discord.ui.Button(
                label=app["label"],
                emoji=app["emoji"],
                style=discord.ButtonStyle.primary,
                custom_id=f"app:open:{app['id']}",
            )
            btn.callback = self._make_callback(app["id"])
            self.add_item(btn)

    def _make_callback(self, app_id: str):
        async def callback(interaction: discord.Interaction):
            cfg = _get_app_config(app_id)
            if not cfg:
                return await interaction.response.send_message("❌ Application type not found.", ephemeral=True)
            modal = build_modal(cfg, interaction.user)
            await interaction.response.send_modal(modal)
        return callback


# ════════════════════════════════════════════════════════════════════════════
# Cog
# ════════════════════════════════════════════════════════════════════════════

class MemberApplications(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(MemberApplicationPanelView())

    @app_commands.command(name="member-application-panel", description="Post the application panel in this channel")
    @has_any_role(ADMIN_ROLE_ID)
    async def application_panel(self, interaction: discord.Interaction):
        types_list = "\n".join(f"{a['emoji']} **{a['label']}**" for a in MEMBER_APPLICATIONS)
        embed = discord.Embed(
            title="📋 Server Applications",
            description=(
                "Interested in joining the team? Click the button for the role you'd like to apply for!\n\n"
                f"{types_list}"
            ),
            colour=0x5865F2,
        )
        embed.set_footer(text=f"{interaction.guild.name} • Applications")
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        await interaction.channel.send(embed=embed, view=MemberApplicationPanelView())
        await interaction.response.send_message("✅ Application panel posted.", ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have the required role.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MemberApplications(bot))

class StaffApplications(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(MemberApplicationPanelView())

    @app_commands.command(name="staff-application-panel", description="Post the application panel in this channel")
    @has_any_role(ADMIN_ROLE_ID)
    async def application_panel(self, interaction: discord.Interaction):
        types_list = "\n".join(f"{a['emoji']} **{a['label']}**" for a in STAFF_APPLICATIONS)
        embed = discord.Embed(
            title="📋 Server Applications",
            description=(
                "Interested in joining the team? Click the button for the role you'd like to apply for!\n\n"
                f"{types_list}"
            ),
            colour=0x5865F2,
        )
        embed.set_footer(text=f"{interaction.guild.name} • Applications")
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        await interaction.channel.send(embed=embed, view=StaffApplicationPanelView())
        await interaction.response.send_message("✅ Application panel posted.", ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have the required role.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffApplications(bot))
