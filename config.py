# ══════════════════════════════════════════════════════════════════════════════
# config.py — Bot configuration and role permission system
# ══════════════════════════════════════════════════════════════════════════════
#
# HOW TO GET A ROLE ID:
#   1. Enable Developer Mode: User Settings → Advanced → Developer Mode
#   2. Go to Server Settings → Roles
#   3. Right-click a role → Copy Role ID
#   4. Paste it below

import discord
from discord import app_commands

# ── Role IDs ──────────────────────────────────────────────────────────────────
ADMIN_ROLE_ID     = 1117190624853110925  # Full access to all commands
MODERATOR_ROLE_ID = 1117190992316076082  # Access to most mod commands
HELPER_ROLE_ID    = 1117191230485438584  # Access to basic commands (warn, purge)

# ── Log channel ───────────────────────────────────────────────────────────────
LOG_CHANNEL_NAME = "logs"   # Name of your log channel
LOG_CHANNEL_ID   = 1117368916528865413     # Or set a specific channel ID (int) to override name

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