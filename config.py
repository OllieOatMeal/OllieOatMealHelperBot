import discord
from discord import app_commands

# ── Role IDs ──────────────────────────────────────────────────────────────────
OWNER_ROLE_ID          = 1117190277522804826  
HEAD_ADMIN_ROLE_ID     = 1117190624853110925  
ADMIN_ROLE_ID          = 1117190992316076082  
STAFF_ROLE_ID          = 1117193288051601508  
TICKET_SUPPORT_ROLE_ID = 1117196652994904154

# ── Log channels ──────────────────────────────────────────────────────────────
LOG_CHANNEL_NAME     = "logs"            
LOG_CHANNEL_ID       = 1117368916528865413  

MOD_LOG_CHANNEL_NAME = "mod-logs"        
MOD_LOG_CHANNEL_ID   = 1117369107898179644  

# ── Ticket system ─────────────────────────────────────────────────────────────
TICKET_CATEGORY_NAME    = "🎫| TICKETS"      
TICKET_LOG_CHANNEL_NAME = "ticket-logs"     
TICKET_SUPPORT_ROLE_ID  = TICKET_SUPPORT_ROLE_ID  

# ── Application system ────────────────────────────────────────────────────────
MEMBER_APPLICATION_LOG_CHANNEL_NAME = "application-logs"  
MEMBER_APPLICATION_PING_ROLE_ID     = ADMIN_ROLE_ID  
STAFF_APPLICATION_LOG_CHANNEL_NAME  = "promotion-applications" 
STAFF_APPLICATION_PING_ROLE_ID      = OWNER_ROLE_ID 

# ── Reusable role check ───────────────────────────────────────────────────────
def has_any_role(*role_ids: int):
    async def predicate(interaction: discord.Interaction) -> bool:
        user_role_ids = {r.id for r in interaction.user.roles}
        if not user_role_ids.intersection(role_ids):
            raise app_commands.CheckFailure("You don't have the required role.")
        return True
    return app_commands.check(predicate)
