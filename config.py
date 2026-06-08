import discord
from discord import app_commands

# ── Role IDs ──────────────────────────────────────────────────────────────────
# Replace these with the actual role IDs from your Discord server.
OWNER_ROLE_ID          = 1117190277522804826
HEAD_ADMIN_ROLE_ID     = 1117190624853110925
ADMIN_ROLE_ID          = 1117190992316076082
TRAINEE_ROLE_ID        = 1117191230485438584
STAFF_ROLE_ID          = 1117193288051601508
TICKET_SUPPORT_ROLE_ID = 1117196652994904154
HELPER_ROLE_ID         = 1117196806309298246

# Ordered list used for rank comparisons (lowest → highest)
STAFF_RANK_ORDER = [
    HELPER_ROLE_ID,
    TRAINEE_ROLE_ID,
    ADMIN_ROLE_ID,
    HEAD_ADMIN_ROLE_ID,
    OWNER_ROLE_ID,
]

# Human-readable names matching each role ID above
STAFF_RANK_NAMES = {
    HELPER_ROLE_ID:     "Helper",
    STAFF_ROLE_ID:      "Staff",
    TRAINEE_ROLE_ID:    "Trainee",
    ADMIN_ROLE_ID:      "Admin",
    HEAD_ADMIN_ROLE_ID: "Head Admin",
    OWNER_ROLE_ID:      "Owner",
}

# ── Log channels ──────────────────────────────────────────────────────────────
LOG_CHANNEL_NAME    = "logs"
LOG_CHANNEL_ID      = 1117368916528865413

MOD_LOG_CHANNEL_NAME = "mod-logs"
MOD_LOG_CHANNEL_ID   = 1117369107898179644

# Channel where staff promotions/demotions are announced
RANK_CHANGES_CHANNEL_NAME = "rank-changes"
RANK_CHANGES_CHANNEL_ID   = 1513298605270761592

# ── Ticket system ─────────────────────────────────────────────────────────────
TICKET_CATEGORY_NAME    = "🎫| TICKETS"
TICKET_LOG_CHANNEL_NAME = "ticket-logs"

# ── Application system ────────────────────────────────────────────────────────
MEMBER_APPLICATION_LOG_CHANNEL_NAME = "application-logs"
MEMBER_APPLICATION_PING_ROLE_ID     = HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID

# STAFF_APPLICATION_LOG_CHANNEL_NAME  = "promotion-applications"
# STAFF_APPLICATION_PING_ROLE_ID      = OWNER_ROLE_ID

# ── Support command ───────────────────────────────────────────────────────────
# Customise the text/links shown when someone runs /support.
FAQ_DESCRIPTION = (
    "Need help? Please review the FAQs:\n\n"
    "📖 **Read the FAQ** <#1199105336750129272> — check our pinned messages for common questions\n\n"
)
REPORT_DESCRIPTION = (
    "Need help reporting a user or staff member? Heres how:\n\n"
    "🎫 **Open a ticket** — use `/ticket` or the ticket panel in <#1117369321040138260>\n"
    "Please be patient — our team will get back to you as soon as possible!"
)
SUPPORT_COLOUR = 0x5865F2  # Discord blurple


# ── Reusable role check ───────────────────────────────────────────────────────
def has_any_role(*role_ids: int):
    """
    Slash-command check decorator.
    Raises CheckFailure if the invoking user has none of the given role IDs.
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        user_role_ids = {r.id for r in interaction.user.roles}
        if not user_role_ids.intersection(role_ids):
            raise app_commands.CheckFailure("You don't have the required role.")
        return True
    return app_commands.check(predicate)
