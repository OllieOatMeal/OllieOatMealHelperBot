# ══════════════════════════════════════════════════════════════════════════════
# config.py — Bot configuration and role permission system
# ══════════════════════════════════════════════════════════════════════════════
#
# HOW TO GET A ROLE / CHANNEL ID:
#   1. Enable Developer Mode: User Settings → Advanced → Developer Mode
#   2. Right-click a role or channel → Copy ID

import discord
from discord import app_commands

# ── Role IDs ──────────────────────────────────────────────────────────────────
OWNER_ROLE_ID          = 1117190277522804826  # Full access to all commands
HEAD_ADMIN_ROLE_ID     = 1117190624853110925  # Full access to all commands
ADMIN_ROLE_ID          = 1117190992316076082  # Access to most mod commands
STAFF_ROLE_ID          = 1117193288051601508  # Access to basic commands (warn, purge)
TICKET_SUPPORT_ROLE_ID = 1117196652994904154

# ── Log channels ──────────────────────────────────────────────────────────────
LOG_CHANNEL_NAME     = "logs"            # General event log channel name
LOG_CHANNEL_ID       = 1117368916528865413  # General log channel ID (overrides name)

MOD_LOG_CHANNEL_NAME = "mod-logs"        # Moderation action log channel name
MOD_LOG_CHANNEL_ID   = 1117369107898179644  # Set to your #mod-logs channel ID (int), or leave 0 to use name

# ── Ticket system ─────────────────────────────────────────────────────────────
TICKET_CATEGORY_NAME    = "🎫| TICKETS"      # Category where ticket channels are created
TICKET_LOG_CHANNEL_NAME = "ticket-logs"     # Channel to log ticket open/close events
TICKET_SUPPORT_ROLE_ID  = TICKET_SUPPORT_ROLE_ID  # Role that can see & manage tickets

# ── Application system ────────────────────────────────────────────────────────
MEMBER_APPLICATION_LOG_CHANNEL_NAME = "application-logs"  # Channel where completed applications are posted
MEMBER_APPLICATION_PING_ROLE_ID     = ADMIN_ROLE_ID  # Role pinged when a new application arrives
STAFF_APPLICATION_LOG_CHANNEL_NAME  = "promotion-applications" # Channel where completed applications are posted
STAFF_APPLICATION_PING_ROLE_ID      = OWNER_ROLE_ID # Role pinged when a new application arrives

# ── Reusable role check ───────────────────────────────────────────────────────
def has_any_role(*role_ids: int):
    """
    Slash command decorator — passes if the user has at least one of the given role IDs.

    Usage:
        @has_any_role(MODERATOR_ROLE_ID, ADMIN_ROLE_ID)
        async def my_command(self, interaction): ...
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        user_role_ids = {r.id for r in interaction.user.roles}
        if not user_role_ids.intersection(role_ids):
            raise app_commands.CheckFailure("You don't have the required role.")
        return True
    return app_commands.check(predicate)
