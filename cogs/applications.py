# ══════════════════════════════════════════════════════════════════════════════
# cogs/applications.py — Application system
# ══════════════════════════════════════════════════════════════════════════════
#
# FEATURES:
#   • Member & Staff application panels with per-type buttons
#   • Accept / Decline / On Hold review buttons for staff
#   • Accepting an application automatically assigns configured role(s)
#   • DM management: /dm <user> <message> to send bot DMs
#   • In-Discord application builder: /app-builder to create, edit, delete
#     application types without touching code — saved to data/applications.json
#   • Blacklist integration: blacklisted users cannot submit applications
#
# COMMANDS:
#   /member-application-panel  — post the member application panel
#   /staff-application-panel   — post the staff application panel
#   /dm <user> <message>       — send a DM to a user via the bot
#   /app-builder               — manage application types in Discord
# ══════════════════════════════════════════════════════════════════════════════

import json
import os
import asyncio
from discord import HTTPException
from datetime import datetime, timezone
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from cogs.blacklist import is_blacklisted
from config import (
    has_any_role, CMD, PERMS,
    HEAD_ADMIN_ROLE_ID, STAFF_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID,
    MEMBER_APPLICATION_LOG_CHANNEL_NAME, MEMBER_APPLICATION_PING_ROLE_ID
)

LEVEL_ROLE_IDS = [
    1117194557554167900,
    1117194754493526156,
    1117195060551876741,
    1117195277036695635
]

# ── Persistent storage ────────────────────────────────────────────────────────

DATA_DIR  = "data"
APP_FILE  = os.path.join(DATA_DIR, "applications.json")
os.makedirs(DATA_DIR, exist_ok=True)

def _load_apps() -> dict:
    """Load {member: [...], staff: [...], open: {app_id: bool}} from JSON."""
    try:
        with open(APP_FILE, "r") as f:
            data = json.load(f)
        # Ensure open map exists
        if "open" not in data:
            data["open"] = {}
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"member": _default_member_apps(), "open": {}}

def _is_open(app_id: str) -> bool:
    """Return True if an application is open (default: True)."""
    return _load_apps()["open"].get(app_id, True)

def _set_open(app_id: str, value: bool):
    data = _load_apps()
    data["open"][app_id] = value
    _save_apps(data)

def _save_apps(data: dict):
    with open(APP_FILE, "w") as f:
        json.dump(data, f, indent=2)

def _default_member_apps() -> list:
    return [
        {
            "id": "staff", "label": "Staff", "emoji": "🛡️", "colour": 0x5865F2,
            "accept_role_ids": [],
            "questions": [
                {"label": "What is your age?",                        "placeholder": "e.g. 18",             "style": "short",     "required": True,  "max_length": 4},
                {"label": "What timezone are you in?",                "placeholder": "e.g. GMT+1, EST…",    "style": "short",     "required": True,  "max_length": 30},
                {"label": "Why do you want to be staff?",             "placeholder": "Tell us your motivation…", "style": "paragraph", "required": True,  "max_length": 500},
                {"label": "Do you have prior moderation experience?", "placeholder": "Describe experience…","style": "paragraph", "required": False, "max_length": 400},
                {"label": "Anything else you'd like us to know?",     "placeholder": "Optional…",           "style": "paragraph", "required": False, "max_length": 300},
            ],
        },
        {
            "id": "helper", "label": "Helper", "emoji": "🤝", "colour": 0x2ECC71,
            "accept_role_ids": [],
            "questions": [
                {"label": "What is your age?",               "placeholder": "e.g. 16",           "style": "short",     "required": True, "max_length": 4},
                {"label": "How active are you on the server?","placeholder": "e.g. 3–4 hours/day","style": "short",    "required": True, "max_length": 100},
                {"label": "Why do you want to be a Helper?", "placeholder": "Explain motivation…","style": "paragraph","required": True, "max_length": 500},
            ],
        },
        {
            "id": "content_creator", "label": "Content Creator", "emoji": "🎥", "colour": 0xF39C12,
            "accept_role_ids": [],
            "questions": [
                {"label": "What content do you produce?",      "placeholder": "e.g. TikToks, YouTube…","style": "paragraph","required": True, "max_length": 300},
                {"label": "How often would you post?",         "placeholder": "e.g. Once a week",     "style": "short",    "required": True, "max_length": 80},
                {"label": "Link something you made:",          "placeholder": "e.g. TikTok/YouTube",  "style": "short",    "required": True, "max_length": 100},
            ],
        },
    ]

def get_apps(panel: str) -> list:
    return _load_apps().get(panel, [])

def get_app_by_id(panel: str, app_id: str) -> dict | None:
    return next((a for a in get_apps(panel) if a["id"] == app_id), None)


# ── Log channel helpers ───────────────────────────────────────────────────────

async def _log_channel(guild: discord.Guild, panel: str) -> discord.TextChannel | None:
    name = MEMBER_APPLICATION_LOG_CHANNEL_NAME
    return discord.utils.get(guild.text_channels, name=name)

def _ping_role_id(panel: str) -> int:
    return MEMBER_APPLICATION_PING_ROLE_ID


# ══════════════════════════════════════════════════════════════════════════════
# Modal
# ══════════════════════════════════════════════════════════════════════════════

def _chunk_questions(questions: list) -> list[list]:
    """Split questions into pages of up to 5 (Discord modal limit)."""
    return [questions[i:i+5] for i in range(0, len(questions), 5)]


async def _post_application(interaction: discord.Interaction, app_cfg: dict,
                             applicant: discord.Member, panel: str, all_answers: dict):
    """Post the completed application embed to the log channel."""
    embed = discord.Embed(
        title=f"{app_cfg['emoji']} {app_cfg['label']} Application",
        colour=app_cfg["colour"],
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_author(name=str(applicant), icon_url=applicant.display_avatar.url)
    embed.add_field(name="Applicant", value=f"{applicant.mention} (`{applicant.id}`)", inline=False)
    for q, a in all_answers.items():
        embed.add_field(name=q, value=a or "*No answer*", inline=False)
    embed.set_footer(text=f"User ID: {applicant.id} | panel:{panel} | app:{app_cfg['id']}")

    log_ch = await _log_channel(interaction.guild, panel)
    if not log_ch:
        await interaction.response.send_message("✅ Application submitted! Staff will review it shortly.", ephemeral=True)
        return

    ping_role = interaction.guild.get_role(_ping_role_id(panel))
    await log_ch.send(
        content=ping_role.mention if ping_role else None,
        embed=embed,
        view=ApplicationReviewView(app_cfg["label"], app_cfg["id"], panel, applicant),
    )
    await interaction.response.send_message(
        embed=discord.Embed(
            title="✅ Application Submitted",
            description=f"Your **{app_cfg['label']}** application has been received!\nYou'll be notified when staff review it.",
            colour=app_cfg["colour"],
        ),
        ephemeral=True,
    )


def build_modal(app_cfg: dict, applicant: discord.Member, panel: str,
                page: int = 0, prior_answers: dict | None = None) -> discord.ui.Modal:
    """
    Build a modal for one page of questions.
    On submit: if more pages remain, sends an ephemeral "Continue" button
    (Discord does not allow responding to a modal with another modal).
    On the final page, posts the full application to the log channel.
    """
    import uuid
    prior_answers  = prior_answers or {}
    pages          = _chunk_questions(app_cfg["questions"])
    total_pages    = len(pages)
    page_questions = pages[page]
    is_last_page   = (page == total_pages - 1)
    page_label     = f" (Part {page+1}/{total_pages})" if total_pages > 1 else ""

    uid         = uuid.uuid4().hex[:8]
    id_to_label = {f"{uid}_{i}": q["label"] for i, q in enumerate(page_questions)}

    class AppModal(discord.ui.Modal):
        def __init__(self):
            super().__init__(title=f"{app_cfg['label']} Application{page_label}")
            for i, q in enumerate(page_questions):
                self.add_item(discord.ui.TextInput(
                    label=q["label"][:45],
                    placeholder=q.get("placeholder", "")[:100],
                    style=discord.TextStyle.paragraph if q.get("style") == "paragraph" else discord.TextStyle.short,
                    required=q.get("required", True),
                    max_length=q.get("max_length", 1024),
                    custom_id=f"{uid}_{i}",
                ))

        async def on_submit(self, interaction: discord.Interaction):
            all_answers = dict(prior_answers)
            for item in self.children:
                label = id_to_label.get(item.custom_id, item.custom_id)
                all_answers[label] = item.value

            if not is_last_page:
                # Discord forbids modal -> modal; send a Continue button instead
                next_page = page + 1
                view = ContinueView(app_cfg, applicant, panel, next_page, all_answers)
                await interaction.response.send_message(
                    content=(
                        f"✅ Part {page+1} saved! Click **Continue** to fill in "
                        f"Part {next_page+1}/{total_pages}."
                    ),
                    view=view,
                    ephemeral=True,
                )
                return

            await _post_application(interaction, app_cfg, applicant, panel, all_answers)

        async def on_error(self, interaction: discord.Interaction, error: Exception):
            print(f"[applications] Modal on_error (page {page}): {error}")
            import traceback; traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Something went wrong submitting your application. Please try again.", ephemeral=True
                )

    return AppModal()


class ContinueView(discord.ui.View):
    """Ephemeral button shown between multi-page modal submissions."""

    def __init__(self, app_cfg: dict, applicant: discord.Member, panel: str,
                 next_page: int, prior_answers: dict):
        import uuid
        super().__init__(timeout=300)
        self.app_cfg        = app_cfg
        self.applicant_id   = applicant.id   # store ID only — Member can go stale
        self.applicant      = applicant
        self.panel          = panel
        self.next_page      = next_page
        self.prior_answers  = prior_answers
        # Give the button a unique custom_id so Discord can route it correctly
        self._btn_id = f"continue:{uuid.uuid4().hex[:12]}"
        # Dynamically add the button with the unique id
        btn = discord.ui.Button(
            label="Continue →",
            style=discord.ButtonStyle.primary,
            emoji="📝",
            custom_id=self._btn_id,
        )
        btn.callback = self._continue_callback
        self.add_item(btn)

    async def _continue_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.applicant_id:
            return await interaction.response.send_message(
                "❌ This isn't your application.", ephemeral=True
            )
        try:
            modal = build_modal(
                self.app_cfg, self.applicant, self.panel,
                page=self.next_page, prior_answers=self.prior_answers,
            )
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"[applications] ContinueView error: {e}")
            import traceback; traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Something went wrong opening the next page. Please try again.", ephemeral=True
                )

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        print(f"[applications] ContinueView on_error: {error}")
        import traceback; traceback.print_exc()
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ Something went wrong. Please try again.", ephemeral=True
            )


# ══════════════════════════════════════════════════════════════════════════════
# Review View  (Accept / Decline / On Hold)
# ══════════════════════════════════════════════════════════════════════════════

class ApplicationReviewView(discord.ui.View):
    def __init__(self, app_label: str, app_id: str, panel: str, applicant: discord.Member):
        super().__init__(timeout=None)
        self.app_label = app_label
        self.app_id    = app_id
        self.panel     = panel
        self.applicant = applicant

    def _is_staff(self, member: discord.Member) -> bool:
        allowed = set(PERMS["dm"])
        return bool({r.id for r in member.roles} & allowed)

    async def _resolve_applicant(self, guild: discord.Guild) -> discord.Member | None:
        if self.applicant and isinstance(self.applicant, discord.Member):
            return self.applicant
        # Try to recover from footer if applicant object is stale
        try:
            embed = None  # resolved in button handlers
            return self.applicant
        except Exception:
            return None

    async def _finalize(self, interaction: discord.Interaction, status: str, colour: int, dm_text: str, assign_roles: bool = False):
        if not self._is_staff(interaction.user):
            return await interaction.response.send_message("❌ Only staff can review applications.", ephemeral=True)

        # Disable all buttons
        for child in self.children:
            child.disabled = True

        original_embed = interaction.message.embeds[0]
        updated = original_embed.copy()
        updated.colour = colour
        updated.add_field(name="Decision", value=f"{status} by {interaction.user.mention}", inline=False)
        await interaction.response.edit_message(embed=updated, view=self)

        # Assign roles on accept
        if assign_roles:
            app_cfg = get_app_by_id(self.panel, self.app_id)
            if app_cfg:
                for role_id in app_cfg.get("accept_role_ids", []):
                    role = interaction.guild.get_role(role_id)
                    if role and self.applicant:
                        try:
                            await self.applicant.add_roles(role, reason=f"Application accepted: {self.app_label}")
                        except discord.Forbidden:
                            pass

        # DM applicant
        if self.applicant:
            try:
                await self.applicant.send(embed=discord.Embed(
                    title=f"{self.app_label} Application — {status}",
                    description=dm_text,
                    colour=colour,
                    timestamp=datetime.now(timezone.utc),
                ))
            except discord.Forbidden:
                pass

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅", custom_id="app:accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._finalize(
            interaction, "✅ Accepted", 0x2ECC71,
            f"🎉 Congratulations! Your **{self.app_label}** application has been **accepted**.\n"
            "A staff member will be in touch shortly.",
            assign_roles=True,
        )

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌", custom_id="app:decline")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._finalize(
            interaction, "❌ Declined", 0xE74C3C,
            f"Thank you for applying for **{self.app_label}**.\n"
            "Unfortunately your application was **not successful** this time.\n"
            "You're welcome to reapply in the future!",
        )

    @discord.ui.button(label="On Hold", style=discord.ButtonStyle.secondary, emoji="⏸️", custom_id="app:onhold")
    async def on_hold(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._finalize(
            interaction, "⏸️ On Hold", 0xF39C12,
            f"Your **{self.app_label}** application has been placed **on hold**.\n"
            "Staff are still reviewing it — we'll get back to you soon.",
        )


# ══════════════════════════════════════════════════════════════════════════════
# Panel Views
# ══════════════════════════════════════════════════════════════════════════════

def _make_panel_view(panel: str) -> discord.ui.View:
    """Build a View with one button per application in the given panel."""
    view = discord.ui.View(timeout=None)
    for app in get_apps(panel):
        btn = discord.ui.Button(
            label=app["label"],
            emoji=app.get("emoji"),
            style=discord.ButtonStyle.primary,
            custom_id=f"app:open:{panel}:{app['id']}",
        )

        def make_cb(a=app, p=panel):
            async def callback(interaction: discord.Interaction):
                if not _is_open(a["id"]):
                    return await interaction.response.send_message(
                        "🔒 Applications for this role are currently **closed**.", ephemeral=True
                    )
                if await is_blacklisted(interaction.user.id, "applications"):
                    return await interaction.response.send_message(
                        "🚫 You are blacklisted from submitting applications.", ephemeral=True
                    )
                member_role_ids = {role.id for role in interaction.user.roles}
                if not member_role_ids.intersection(LEVEL_ROLE_IDS):
                    return await interaction.response.send_message(
                        "❌ You don't have the required role (Level 10+) to apply.", ephemeral=True
                    )
                cfg = get_app_by_id(p, a["id"])
                if not cfg:
                    return await interaction.response.send_message(
                        "❌ Application type not found.", ephemeral=True
                    )
                await interaction.response.send_modal(build_modal(cfg, interaction.user, p))
            return callback

        btn.callback = make_cb()
        view.add_item(btn)
    return view

# ══════════════════════════════════════════════════════════════════════════════
# App Builder Modals
# ══════════════════════════════════════════════════════════════════════════════

class CreateAppModal(discord.ui.Modal, title="Create Application Type"):
    app_id    = discord.ui.TextInput(label="ID (no spaces, unique)",       placeholder="e.g. moderator",   max_length=32)
    label     = discord.ui.TextInput(label="Button Label",                  placeholder="e.g. Moderator",   max_length=32)
    emoji     = discord.ui.TextInput(label="Emoji",                         placeholder="e.g. 🛡️",          max_length=10, required=False)
    panel     = discord.ui.TextInput(label='Panel ("member" or "staff")',   placeholder="member",           max_length=10)
    role_ids  = discord.ui.TextInput(
        label="Accept Role IDs (comma-separated)",
        placeholder="e.g. 123456789, 987654321  (leave blank for none)",
        required=False, style=discord.TextStyle.short, max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        panel = self.panel.value.strip().lower()
        if panel not in ("member", "staff"):
            return await interaction.response.send_message("❌ Panel must be `member` or `staff`.", ephemeral=True)

        data = _load_apps()
        existing_ids = [a["id"] for a in data.get(panel, [])]
        new_id = self.app_id.value.strip().lower().replace(" ", "_")

        if new_id in existing_ids:
            return await interaction.response.send_message(f"❌ An application with ID `{new_id}` already exists in **{panel}**.", ephemeral=True)

        # Parse role IDs
        role_ids = []
        for part in self.role_ids.value.split(","):
            part = part.strip()
            if part.isdigit():
                role_ids.append(int(part))

        new_app = {
            "id":             new_id,
            "label":          self.label.value.strip(),
            "emoji":          self.emoji.value.strip() or "📋",
            "colour":         0x5865F2,
            "accept_role_ids": role_ids,
            "questions":      [
                {"label": "Tell us about yourself.", "placeholder": "Edit questions via /app-builder edit", "style": "paragraph", "required": True, "max_length": 1000},
            ],
        }

        data.setdefault(panel, []).append(new_app)
        _save_apps(data)

        role_mentions = ", ".join(f"`{r}`" for r in role_ids) if role_ids else "None"
        await interaction.response.send_message(
            embed=discord.Embed(
                title="✅ Application Created",
                description=(
                    f"**ID:** `{new_id}`\n**Label:** {new_app['label']}\n"
                    f"**Panel:** {panel}\n**Accept Roles:** {role_mentions}\n\n"
                    "⚠️ It has a placeholder question. Re-post the panel with `/member-application-panel` or `/staff-application-panel` to activate it.\n"
                    "Edit questions by modifying `data/applications.json` directly, or use `/app-builder edit-roles` to update roles."
                ),
                colour=0x2ECC71,
            ),
            ephemeral=True,
        )


class EditRolesModal(discord.ui.Modal, title="Edit Accept Roles"):
    app_id   = discord.ui.TextInput(label="Application ID",                         placeholder="e.g. staff",       max_length=32)
    panel    = discord.ui.TextInput(label='Panel ("member" or "staff")',             placeholder="member",           max_length=10)
    role_ids = discord.ui.TextInput(
        label="Accept Role IDs (comma-separated)",
        placeholder="e.g. 123456789, 987654321  (leave blank to clear)",
        required=False, style=discord.TextStyle.short, max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        panel = self.panel.value.strip().lower()
        if panel not in ("member", "staff"):
            return await interaction.response.send_message("❌ Panel must be `member` or `staff`.", ephemeral=True)

        data   = _load_apps()
        app_id = self.app_id.value.strip().lower()
        apps   = data.get(panel, [])
        app    = next((a for a in apps if a["id"] == app_id), None)

        if not app:
            return await interaction.response.send_message(f"❌ No application `{app_id}` found in **{panel}**.", ephemeral=True)

        role_ids = []
        for part in self.role_ids.value.split(","):
            part = part.strip()
            if part.isdigit():
                role_ids.append(int(part))

        app["accept_role_ids"] = role_ids
        _save_apps(data)

        role_strs = []
        for rid in role_ids:
            role = interaction.guild.get_role(rid)
            role_strs.append(role.mention if role else f"`{rid}`")

        await interaction.response.send_message(
            embed=discord.Embed(
                title="✅ Accept Roles Updated",
                description=f"**{app['label']}** will now assign: {', '.join(role_strs) or 'None'}",
                colour=0x2ECC71,
            ),
            ephemeral=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Cog
# ══════════════════════════════════════════════════════════════════════════════

class Applications(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Re-register persistent views so buttons work after restart
        bot.add_view(_make_panel_view("member"))
        bot.add_view(_make_panel_view("staff"))

    # ── /member-application-panel ─────────────────────────────────────────────

    @app_commands.command(name=CMD["member_application_panel"], description="Post the member application panel in this channel")
    @has_any_role(*PERMS["member_application_panel"])
    async def member_panel(self, interaction: discord.Interaction):
        apps = get_apps("member")
        if not apps:
            return await interaction.response.send_message("❌ No member applications configured.", ephemeral=True)
        types_list = "\n".join(f"{a.get('emoji','📋')} **{a['label']}**" for a in apps)
        embed = discord.Embed(
            title="📋 Server Applications",
            description=f"Interested in joining the team? Click the button for the role you'd like to apply for!\n\n{types_list}",
            colour=0x5865F2,
        )
        embed.set_footer(text=f"{interaction.guild.name} • Applications")
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        await interaction.channel.send(embed=embed, view=_make_panel_view("member"))
        await interaction.response.send_message("✅ Member application panel posted.", ephemeral=True)

    # ── /staff-application-panel ──────────────────────────────────────────────

    @app_commands.command(name=CMD["staff_application_panel"], description="Post the staff application panel in this channel")
    @has_any_role(*PERMS["staff_application_panel"])
    async def staff_panel(self, interaction: discord.Interaction):
        apps = get_apps("staff")
        if not apps:
            return await interaction.response.send_message("❌ No staff applications configured.", ephemeral=True)
        types_list = "\n".join(f"{a.get('emoji','📋')} **{a['label']}**" for a in apps)
        embed = discord.Embed(
            title="📋 Staff Applications",
            description=f"Click the button below to submit your application!\n\n{types_list}",
            colour=0xF39C12,
        )
        embed.set_footer(text=f"{interaction.guild.name} • Staff Applications")
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        await interaction.channel.send(embed=embed, view=_make_panel_view("staff"))
        await interaction.response.send_message("✅ Staff application panel posted.", ephemeral=True)

    # ── /dm ───────────────────────────────────────────────────────────────────

    @app_commands.command(name=CMD["dm"], description="Send a DM to a user via the bot")
    @app_commands.describe(user="The user to DM", message="The message to send")
    @has_any_role(*PERMS["dm"])
    async def dm_user(self, interaction: discord.Interaction, user: discord.Member, message: str):
        await interaction.response.defer(ephemeral=True)  # ← defer first, DM can be slow

        embed = discord.Embed(
            title=f"📬 Message from {interaction.guild.name}",
            description=message,
            colour=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Sent by {interaction.user} • {interaction.guild.name}")
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        try:
            dm_channel = await user.create_dm()   # ← explicitly create/fetch the DM channel
            await asyncio.sleep(1)                # ← small delay to avoid 40003
            await dm_channel.send(embed=embed)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="✅ DM Sent",
                    description=f"Message delivered to {user.mention}.",
                    colour=0x2ECC71,
                ),
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"❌ Could not DM {user.mention} — they may have DMs disabled.", ephemeral=True
            )
        except HTTPException as e:
            await interaction.followup.send(
                f"❌ Failed to send DM: {e.text}", ephemeral=True
            )

    # ── /app-builder ──────────────────────────────────────────────────────────

    application = app_commands.Group(
        name=CMD["application"],
        description="Manage application types within Discord",
    )

    @application.command(name=CMD["application_list"], description="List all configured application types")
    @has_any_role(*PERMS["application"])
    async def builder_list(self, interaction: discord.Interaction):
        data = _load_apps()
        embed = discord.Embed(title="📋 Application Types", colour=0x5865F2, timestamp=datetime.now(timezone.utc))
        for panel_name in ("member", "staff"):
            apps = data.get(panel_name, [])
            if apps:
                lines = []
                for a in apps:
                    role_ids = a.get("accept_role_ids", [])
                    roles    = ", ".join(f"<@&{r}>" for r in role_ids) if role_ids else "None"
                    lines.append(f"**`{a['id']}`** — {a.get('emoji','')} {a['label']} | Accept roles: {roles} | {len(a.get('questions',[]))} question(s)")
                embed.add_field(name=f"{panel_name.capitalize()} Panel", value="\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @application.command(name=CMD["application_create"], description="Create a new application type")
    @has_any_role(*PERMS["application"])
    async def builder_create(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateAppModal())

    @application.command(name=CMD["application_delete"], description="Delete an application type")
    @app_commands.describe(panel='Panel to delete from ("member" or "staff")', app_id="Application ID to delete")
    @has_any_role(*PERMS["application"])
    async def builder_delete(self, interaction: discord.Interaction, panel: Literal["member", "staff"], app_id: str):
        data = _load_apps()
        apps = data.get(panel, [])
        match = next((a for a in apps if a["id"] == app_id), None)
        if not match:
            return await interaction.response.send_message(f"❌ No application `{app_id}` found in **{panel}**.", ephemeral=True)
        data[panel] = [a for a in apps if a["id"] != app_id]
        _save_apps(data)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🗑️ Application Deleted",
                description=f"Removed **{match['label']}** (`{app_id}`) from the **{panel}** panel.\nRe-post the panel to update.",
                colour=0xE74C3C,
            ),
            ephemeral=True,
        )

    @application.command(name=CMD["application_edit_roles"], description="Set which roles are assigned when an application is accepted")
    @has_any_role(*PERMS["application"])
    async def builder_edit_roles(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditRolesModal())

    @application.command(name=CMD["application_open"], description="Open an application type so users can submit")
    @app_commands.describe(app_id="Application ID to open (use /app-builder list to see IDs)")
    @has_any_role(*PERMS["application"])
    async def builder_open(self, interaction: discord.Interaction, app_id: str):
        # Find the app across both panels
        data = _load_apps()
        match = next((a for panel in ("member","staff") for a in data.get(panel,[]) if a["id"] == app_id), None)
        if not match:
            return await interaction.response.send_message(f"❌ No application with ID `{app_id}` found.", ephemeral=True)
        _set_open(app_id, True)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🟢 Applications Opened",
                description=f"**{match['label']}** applications are now **open**. Users can submit.",
                colour=0x2ECC71,
            ),
            ephemeral=True,
        )

    @application.command(name=CMD["application_close"], description="Close an application type so users cannot submit")
    @app_commands.describe(app_id="Application ID to close (use /app-builder list to see IDs)")
    @has_any_role(*PERMS["application"])
    async def builder_close(self, interaction: discord.Interaction, app_id: str):
        data = _load_apps()
        match = next((a for panel in ("member","staff") for a in data.get(panel,[]) if a["id"] == app_id), None)
        if not match:
            return await interaction.response.send_message(f"❌ No application with ID `{app_id}` found.", ephemeral=True)
        _set_open(app_id, False)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔴 Applications Closed",
                description=f"**{match['label']}** applications are now **closed**. Users will see a closed message.",
                colour=0xE74C3C,
            ),
            ephemeral=True,
        )

    @application.command(name=CMD["application_status"], description="Show open/closed status of all application types")
    @has_any_role(*PERMS["application_status"])
    async def builder_status(self, interaction: discord.Interaction):
        data = _load_apps()
        embed = discord.Embed(title="📋 Application Status", colour=0x5865F2, timestamp=datetime.now(timezone.utc))
        for panel_name in ("member", "staff"):
            apps = data.get(panel_name, [])
            if apps:
                lines = []
                for a in apps:
                    is_open = data["open"].get(a["id"], True)
                    status  = "🟢 Open" if is_open else "🔴 Closed"
                    lines.append(f"{status} — {a.get('emoji','')} **{a['label']}** (`{a['id']}`)")
                embed.add_field(name=f"{panel_name.capitalize()} Panel", value="\n".join(lines), inline=False)
        if not any(data.get(p) for p in ("member","staff")):
            embed.description = "No application types configured."
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Error handler ─────────────────────────────────────────────────────────

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ You don't have the required role.", ephemeral=True)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)
            raise error


# ── Setup ─────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    # Warn on startup about any labels that had to be truncated
    data = _load_apps()
    for panel_name in ("member", "staff"):
        for app in data.get(panel_name, []):
            for q in app.get("questions", []):
                if len(q.get("label", "")) > 45:
                    print(f"[applications] WARNING: question label too long (will be truncated) in '{app['id']}': {q['label']!r}")
    await bot.add_cog(Applications(bot))
    print("Applications cog loaded")