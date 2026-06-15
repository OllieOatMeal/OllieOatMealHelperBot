import discord
from discord import app_commands

# ══════════════════════════════════════════════════════════════════════════════
# ROLE IDs
# Replace these with the actual role IDs from your Discord server.
# ══════════════════════════════════════════════════════════════════════════════

ROLES = {
    "OWNER":           1117190277522804826,
    "MANAGER":         1117190624853110925,
    "HEAD_ADMIN":      1117190992316076082,
    "ADMIN":           1117191230485438584,
    "STAFF":           1117193288051601508,
    "TICKET_SUPPORT":  1117196652994904154,
    "INTERNAL_AFFAIRS":1516194876860006581,
    "HELPER":          1117196806309298246,
    "MUSIC_DJ":        1117193408105164902,
}

# Shorthand aliases so the rest of the code stays readable

OWNER_ROLE_ID            = ROLES["OWNER"]
MANAGER_ROLE_ID          = ROLES["MANAGER"]
HEAD_ADMIN_ROLE_ID       = ROLES["HEAD_ADMIN"]
ADMIN_ROLE_ID            = ROLES["ADMIN"]
STAFF_ROLE_ID            = ROLES["STAFF"]
TICKET_SUPPORT_ROLE_ID   = ROLES["TICKET_SUPPORT"]
INTERNAL_AFFAIRS_ROLE_ID = ROLES["INTERNAL_AFFAIRS"]
HELPER_ROLE_ID           = ROLES["HELPER"]
MUSIC_DJ_ROLE_ID         = ROLES["MUSIC_DJ"]

# Ordered list used for rank comparisons (lowest → highest)

STAFF_RANK_ORDER = [
    HELPER_ROLE_ID,
    STAFF_ROLE_ID,
    ADMIN_ROLE_ID,
    HEAD_ADMIN_ROLE_ID,
    MANAGER_ROLE_ID,
    OWNER_ROLE_ID,
]

# Human-readable names matching each role ID above

STAFF_RANK_NAMES = {
    HELPER_ROLE_ID:     "Helper",
    STAFF_ROLE_ID:      "Staff",
    ADMIN_ROLE_ID:      "Admin",
    HEAD_ADMIN_ROLE_ID: "Head Admin",
    MANAGER_ROLE_ID:    "Manager",
    OWNER_ROLE_ID:      "Owner",
}

# ══════════════════════════════════════════════════════════════════════════════
# COMMAND NAMES
# Change any value here to rename a slash command across the whole bot.
# ══════════════════════════════════════════════════════════════════════════════

CMD = {
    # info_commands
    "post_rules":               "post-rules",
    "post_roles":               "post-roles",

    # utility
    "support":                  "support",
    "rolegive":                 "rolegive",
    "roleremove":               "roleremove",
    "promote":                  "promote",
    "demote":                   "demote",
    "staffrank":                "staffrank",

    # moderation
    "ban":                      "ban",
    "unban":                    "unban",
    "kick":                     "kick",
    "mute":                     "mute",
    "unmute":                   "unmute",
    "warn":                     "warn",
    "warnings":                 "warnings",
    "clearwarns":               "clearwarns",
    "purge":                    "purge",
    "lock":                     "lock",
    "unlock":                   "unlock",
    "slowmode":                 "slowmode",
    "nick":                     "nick",

    # embeds  (group name + subcommands)
    "embed":                    "embed",
    "embed_simple":             "simple",
    "embed_builder":            "builder",
    "embed_announce":           "announce",
    "embed_rules":              "rules",
    "embed_edit":               "edit",

    # applications (group name + subcommands)
    # FIX: "application" is the key applications.py uses for the group name;
    #      "application_builder" is kept as an alias pointing to the same string.
    "application":              "app-builder",   # used by applications.py group registration
    "application_builder":      "app-builder",   # legacy alias — same slash-command name
    "member_application_panel": "member-application-panel",
    "staff_application_panel":  "staff-application-panel",
    "dm":                       "dm",
    "application_list":         "list",          # FIX: was "applications_list", key missing
    "applications_list":        "list",          # legacy alias
    "application_create":       "create",
    "application_delete":       "delete",
    "application_edit_roles":   "edit-roles",
    "application_open":         "open",
    "application_close":        "close",
    "application_status":       "status",

    # blacklist (group name + subcommands)
    "blacklist":                "blacklist",
    "blacklist_add":            "add",
    "blacklist_remove":         "remove",
    "blacklist_check":          "check",
    "blacklist_list":           "list",

    # tickets
    "ticket_panel":             "ticket-panel",
    "ticket_close":             "ticket-close",

    # logging
    "setlogchannel":            "setlogchannel",

    # reaction roles (group + subcommands)
    "reactionrole":             "reactionrole",
    "rr_add":                   "add",
    "rr_create":                "create",
    "rr_edit":                  "edit",
    "rr_remove":                "remove",
    "rr_list":                  "list",

    # music
    "play":                     "play",
    "music_panel":              "music-panel",
    "stop":                     "stop",
    "queue":                    "queue",
    "skip":                     "skip",
    "pause":                    "pause",
    "resume":                   "resume",
    "volume":                   "volume",
    "shuffle":                  "shuffle",
    "loop":                     "loop",
    "leave":                    "leave",
}

# ══════════════════════════════════════════════════════════════════════════════
# COMMAND PERMISSIONS
# Each key is a CMD key; value is a tuple of role IDs that can run it.
# Roles higher in STAFF_RANK_ORDER do NOT automatically inherit lower perms —
# list every role that should have access.
# ══════════════════════════════════════════════════════════════════════════════

PERMS = {
    # info_commands
    "post_rules":               (MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "post_roles":               (MANAGER_ROLE_ID, OWNER_ROLE_ID),

    # utility
    "support":                  (STAFF_ROLE_ID, HELPER_ROLE_ID),
    "rolegive":                 (MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "roleremove":               (MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "promote":                  (MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "demote":                   (MANAGER_ROLE_ID, OWNER_ROLE_ID),
    # staffrank has no permission check (visible to everyone)

    # moderation
    "ban":                      (HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "unban":                    (MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "kick":                     (STAFF_ROLE_ID, HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "mute":                     (STAFF_ROLE_ID, HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "unmute":                   (HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "warn":                     (STAFF_ROLE_ID, HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "warnings":                 (STAFF_ROLE_ID, HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "clearwarns":               (MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "purge":                    (HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "lock":                     (MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "unlock":                   (MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "slowmode":                 (MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "nick":                     (STAFF_ROLE_ID, HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),

    # embeds — all subcommands share the same permission
    "embed":                    (MANAGER_ROLE_ID, OWNER_ROLE_ID),

    # applications
    # FIX: added "application" and "application_status" keys that applications.py expects
    "application":              (HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "application_status":       (STAFF_ROLE_ID, HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "app_builder":              (HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),  # legacy alias
    "app_builder_status":       (STAFF_ROLE_ID, HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),  # legacy alias
    "member_application_panel": (HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "staff_application_panel":  (HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "dm":                       (STAFF_ROLE_ID, HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),

    # blacklist
    "blacklist":                (STAFF_ROLE_ID, HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),

    # tickets
    "ticket_panel":             (MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "ticket_close":             (TICKET_SUPPORT_ROLE_ID,),

    # logging
    "setlogchannel":            (OWNER_ROLE_ID,),

    # music — controlled by MUSIC_DJ_ROLE_ID + staff (see music.py)
    "music":                    (MUSIC_DJ_ROLE_ID, STAFF_ROLE_ID, ADMIN_ROLE_ID,
                                 HEAD_ADMIN_ROLE_ID, MANAGER_ROLE_ID, OWNER_ROLE_ID),
    "music_panel":              (MANAGER_ROLE_ID, OWNER_ROLE_ID),

    # reaction roles — all subcommands share same permission
    "reactionrole":             (OWNER_ROLE_ID,),
}

# ══════════════════════════════════════════════════════════════════════════════
# LOG CHANNELS
# ══════════════════════════════════════════════════════════════════════════════

LOG_CHANNEL_NAME    = "logs"
LOG_CHANNEL_ID      = 1117368916528865413

MOD_LOG_CHANNEL_NAME = "mod-logs"
MOD_LOG_CHANNEL_ID   = 1117369107898179644

RANK_CHANGES_CHANNEL_NAME = "rank-changes"
RANK_CHANGES_CHANNEL_ID   = 1513298605270761592

# ══════════════════════════════════════════════════════════════════════════════
# TICKET SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

TICKET_CATEGORY_NAME    = "🎫| TICKETS"
TICKET_LOG_CHANNEL_NAME = "ticket-logs"

REPORT_CATAGORY_NAME    = "🎫| TICKETS"
REPORT_LOG_CHANNEL_NAME = "report-logs"

# ══════════════════════════════════════════════════════════════════════════════
# APPLICATION SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

MEMBER_APPLICATION_LOG_CHANNEL_NAME = "application-logs"
# FIX: was `MANAGER_ROLE_ID, OWNER_ROLE_ID` (implicit tuple without parens — confusing).
#      Now an explicit tuple. _post_application iterates over this directly.
MEMBER_APPLICATION_PING_ROLE_IDS    = (MANAGER_ROLE_ID, OWNER_ROLE_ID)

# ══════════════════════════════════════════════════════════════════════════════
# SUPPORT COMMAND TEXT
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# REUSABLE ROLE CHECK
# ══════════════════════════════════════════════════════════════════════════════

def has_any_role(*role_ids: int):
    """
    Slash-command check decorator.
    Raises CheckFailure if the invoking user has none of the given role IDs.
    Usage:  @has_any_role(*PERMS["ban"])
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        user_role_ids = {r.id for r in interaction.user.roles}
        if not user_role_ids.intersection(role_ids):
            raise app_commands.CheckFailure("You don't have the required role.")
        return True
    return app_commands.check(predicate)