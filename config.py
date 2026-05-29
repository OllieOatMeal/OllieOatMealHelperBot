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
ADMIN_ROLE_ID     = 1117190624853110925  # Full access to all commands
MODERATOR_ROLE_ID = 1117190992316076082  # Access to most mod commands
HELPER_ROLE_ID    = 1117191230485438584  # Access to basic commands (warn, purge)

# ── Log channels ──────────────────────────────────────────────────────────────
LOG_CHANNEL_NAME     = "logs"            # General event log channel name
LOG_CHANNEL_ID       = 1117368916528865413  # General log channel ID (overrides name)

MOD_LOG_CHANNEL_NAME = "mod-logs"        # Moderation action log channel name
MOD_LOG_CHANNEL_ID   = 0                 # Set to your #mod-logs channel ID (int), or leave 0 to use name

# ── Ticket system ─────────────────────────────────────────────────────────────
TICKET_CATEGORY_NAME    = "Tickets"      # Category where ticket channels are created
TICKET_LOG_CHANNEL_NAME = "mod-logs"     # Channel to log ticket open/close events
TICKET_SUPPORT_ROLE_ID  = MODERATOR_ROLE_ID  # Role that can see & manage tickets

# ── Application system ────────────────────────────────────────────────────────
APPLICATION_LOG_CHANNEL_NAME = "mod-logs"  # Channel where completed applications are posted
APPLICATION_PING_ROLE_ID     = ADMIN_ROLE_ID  # Role pinged when a new application arrives

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
