"""
cogs/utility.py
────────────────
General-purpose utility commands:
  • /support   — posts a help-seeking embed for regular users
  • /promote   — promotes a staff member to the next rank
  • /demote    — demotes a staff member to the previous rank
  • /staffrank — shows a member's current staff rank (if any)
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from config import (
    has_any_role,
    OWNER_ROLE_ID, HEAD_ADMIN_ROLE_ID, ADMIN_ROLE_ID, STAFF_ROLE_ID, HELPER_ROLE_ID,
    STAFF_RANK_ORDER, STAFF_RANK_NAMES,
    REPORT_DESCRIPTION, SUPPORT_COLOUR,FAQ_DESCRIPTION,
    RANK_CHANGES_CHANNEL_ID, RANK_CHANGES_CHANNEL_NAME,
    MOD_LOG_CHANNEL_ID, MOD_LOG_CHANNEL_NAME,
)


async def _get_rank_changes_channel(guild: discord.Guild) -> discord.TextChannel | None:
    """Locate the rank-changes announcement channel by ID, falling back to name."""
    if RANK_CHANGES_CHANNEL_ID:
        ch = guild.get_channel(RANK_CHANGES_CHANNEL_ID)
        if ch:
            return ch
    return discord.utils.get(guild.text_channels, name=RANK_CHANGES_CHANNEL_NAME)


async def _get_mod_log_channel(guild: discord.Guild) -> discord.TextChannel | None:
    """Locate the mod-log channel by ID, falling back to name."""
    if MOD_LOG_CHANNEL_ID:
        ch = guild.get_channel(MOD_LOG_CHANNEL_ID)
        if ch:
            return ch
    return discord.utils.get(guild.text_channels, name=MOD_LOG_CHANNEL_NAME)


def _get_staff_rank(member: discord.Member) -> int | None:
    """
    Return the index of a member's highest staff role within STAFF_RANK_ORDER.
    Returns None if the member holds no staff roles.
    """
    member_role_ids = {r.id for r in member.roles}
    # Walk the rank list from highest to lowest, return first match
    for i in range(len(STAFF_RANK_ORDER) - 1, -1, -1):
        if STAFF_RANK_ORDER[i] in member_role_ids:
            return i
    return None


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /support ──────────────────────────────────────────────────────────────

    @app_commands.command(name="support", description="Show users how to report someone")
    @has_any_role(STAFF_ROLE_ID, HELPER_ROLE_ID)
    async def support(self, interaction: discord.Interaction):
        """
        Posts a public embed explaining the process to report a user.
        Helper+ can run this command.
        """
        embed = discord.Embed(
            title="🆘 How to Report Someone",
            description=REPORT_DESCRIPTION,
            colour=SUPPORT_COLOUR,
            timestamp=datetime.now(timezone.utc),
        )
        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=interaction.guild.name if interaction.guild else "Report")

        await interaction.response.send_message(embed=embed)

    # ── /faq ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="support", description="Show users how to ask questions")
    @has_any_role(STAFF_ROLE_ID, HELPER_ROLE_ID)
    async def support(self, interaction: discord.Interaction):
        """
        Posts a public embed explaining the faq channel available.
        Helper+ can run this command.
        """
        embed = discord.Embed(
            title="🆘 FAQ Guide",
            description=FAQ_DESCRIPTION,
            colour=SUPPORT_COLOUR,
            timestamp=datetime.now(timezone.utc),
        )
        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=interaction.guild.name if interaction.guild else "FAQ")

        await interaction.response.send_message(embed=embed)

    # ── /rolegive ──────────────────────────────────────────────────────────────

    @app_commands.command(name="rolegive", description="Give a role to a certain user")
    @app_commands.describe(
        member="The member to give the role to",
        role="The role to give the member",
    )
    @has_any_role(HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
    async def rolegive(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
    ):
        await interaction.response.defer(ephemeral=True)

        await member.add_roles(role,reason="Command")
        await interaction.followup.send(
            f"✅ {member.mention} has been given {role.mention}.",
            ephemeral=True,
        )

    # ── /roleremove ──────────────────────────────────────────────────────────────

    @app_commands.command(name="roleremove", description="Removes a role from a certain user")
    @app_commands.describe(
        member="The member to remove the role from",
        role="The role to remove from the member",
    )
    @has_any_role(HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
    async def rolegive(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
    ):
        await interaction.response.defer(ephemeral=True)

        await member.remove_roles(role,reason="Command")
        await interaction.followup.send(
            f"✅ {member.mention} has had removed {role.mention}.",
            ephemeral=True,
        )

    # ── /promote ──────────────────────────────────────────────────────────────

    @app_commands.command(name="promote", description="Promote a staff member to the next rank")
    @app_commands.describe(
        member="The staff member to promote",
        reason="Reason for the promotion (shown in the announcement)",
    )
    @has_any_role(HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
    async def promote(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        """
        Moves a member up by one rank in STAFF_RANK_ORDER.
        - Removes their current staff role
        - Assigns the next role up
        - Announces the promotion in #rank-changes
        - Logs the action in #mod-logs
        """
        await interaction.response.defer(ephemeral=True)

        current_rank = _get_staff_rank(member)

        # Validate the member has a promotable rank
        if current_rank is None:
            return await interaction.followup.send(
                "❌ That member doesn't hold any staff role.", ephemeral=True
            )
        if current_rank >= len(STAFF_RANK_ORDER) - 1:
            return await interaction.followup.send(
                f"❌ {member.mention} is already at the highest staff rank.", ephemeral=True
            )

        old_role_id  = STAFF_RANK_ORDER[current_rank]
        new_role_id  = STAFF_RANK_ORDER[current_rank + 1]
        old_role     = interaction.guild.get_role(old_role_id)
        new_role     = interaction.guild.get_role(new_role_id)

        if not old_role or not new_role:
            return await interaction.followup.send(
                "❌ Could not find one of the rank roles. Check the IDs in config.py.", ephemeral=True
            )

        # Swap the roles
        await member.remove_roles(old_role, reason=f"Promoted by {interaction.user}")
        await member.add_roles(new_role, reason=f"Promoted by {interaction.user}")

        old_name = STAFF_RANK_NAMES[old_role_id]
        new_name = STAFF_RANK_NAMES[new_role_id]

        # Announce in #rank-changes
        rank_ch = await _get_rank_changes_channel(interaction.guild)
        if rank_ch:
            announce = discord.Embed(
                title="⬆️ Staff Promotion",
                colour=0x2ECC71,
                timestamp=datetime.now(timezone.utc),
            )
            announce.add_field(name="Member", value=member.mention, inline=False)
            announce.add_field(name="Promoted From", value=old_name, inline=True)
            announce.add_field(name="Promoted To",   value=new_name, inline=True)
            announce.add_field(name="Reason",        value=reason,   inline=False)
            announce.add_field(name="Promoted By",   value=interaction.user.mention, inline=True)
            announce.set_thumbnail(url=member.display_avatar.url)
            await rank_ch.send(embed=announce)

        # Log in #mod-logs
        log_ch = await _get_mod_log_channel(interaction.guild)
        if log_ch:
            log_embed = discord.Embed(
                title="⬆️ Staff Promoted",
                colour=0x2ECC71,
                timestamp=datetime.now(timezone.utc),
            )
            log_embed.add_field(name="Member",       value=f"{member.mention} (`{member}`)", inline=False)
            log_embed.add_field(name="From Rank",    value=old_name,                         inline=True)
            log_embed.add_field(name="To Rank",      value=new_name,                         inline=True)
            log_embed.add_field(name="Reason",       value=reason,                           inline=False)
            log_embed.add_field(name="Actioned By",  value=interaction.user.mention,         inline=True)
            log_embed.set_thumbnail(url=member.display_avatar.url)
            await log_ch.send(embed=log_embed)

        # Notify the promoted member via DM
        try:
            dm = discord.Embed(
                title="🎉 You've been promoted!",
                description=(
                    f"Congratulations! You have been promoted to **{new_name}** "
                    f"in **{interaction.guild.name}**.\n**Reason:** {reason}"
                ),
                colour=0x2ECC71,
            )
            await member.send(embed=dm)
        except discord.Forbidden:
            pass  # DMs are closed — that's fine

        await interaction.followup.send(
            f"✅ {member.mention} has been promoted from **{old_name}** to **{new_name}**.",
            ephemeral=True,
        )

    # ── /demote ───────────────────────────────────────────────────────────────

    @app_commands.command(name="demote", description="Demote a staff member to the previous rank")
    @app_commands.describe(
        member="The staff member to demote",
        reason="Reason for the demotion (shown in the announcement)",
    )
    @has_any_role(HEAD_ADMIN_ROLE_ID, OWNER_ROLE_ID)
    async def demote(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        """
        Moves a member down by one rank in STAFF_RANK_ORDER.
        If they are at the lowest staff rank they are removed from staff entirely.
        """
        await interaction.response.defer(ephemeral=True)

        current_rank = _get_staff_rank(member)

        if current_rank is None:
            return await interaction.followup.send(
                "❌ That member doesn't hold any staff role.", ephemeral=True
            )

        old_role_id = STAFF_RANK_ORDER[current_rank]
        old_role    = interaction.guild.get_role(old_role_id)
        old_name    = STAFF_RANK_NAMES[old_role_id]

        # Determine the new rank (or full removal if already at the bottom)
        if current_rank == 0:
            # Lowest rank — remove from staff entirely
            new_role     = None
            new_name     = "No Staff Role"
            new_role_id  = None
        else:
            new_role_id = STAFF_RANK_ORDER[current_rank - 1]
            new_role    = interaction.guild.get_role(new_role_id)
            new_name    = STAFF_RANK_NAMES[new_role_id]

        if not old_role:
            return await interaction.followup.send(
                "❌ Could not find the current rank role. Check the IDs in config.py.", ephemeral=True
            )

        # Swap roles
        await member.remove_roles(old_role, reason=f"Demoted by {interaction.user}")
        if new_role:
            await member.add_roles(new_role, reason=f"Demoted by {interaction.user}")

        # Announce in #rank-changes
        rank_ch = await _get_rank_changes_channel(interaction.guild)
        if rank_ch:
            announce = discord.Embed(
                title="⬇️ Staff Demotion",
                colour=0xE74C3C,
                timestamp=datetime.now(timezone.utc),
            )
            announce.add_field(name="Member",       value=member.mention, inline=False)
            announce.add_field(name="Demoted From", value=old_name,       inline=True)
            announce.add_field(name="Demoted To",   value=new_name,       inline=True)
            announce.add_field(name="Reason",       value=reason,         inline=False)
            announce.add_field(name="Demoted By",   value=interaction.user.mention, inline=True)
            announce.set_thumbnail(url=member.display_avatar.url)
            await rank_ch.send(embed=announce)

        # Log in #mod-logs
        log_ch = await _get_mod_log_channel(interaction.guild)
        if log_ch:
            log_embed = discord.Embed(
                title="⬇️ Staff Demoted",
                colour=0xE74C3C,
                timestamp=datetime.now(timezone.utc),
            )
            log_embed.add_field(name="Member",      value=f"{member.mention} (`{member}`)", inline=False)
            log_embed.add_field(name="From Rank",   value=old_name,                         inline=True)
            log_embed.add_field(name="To Rank",     value=new_name,                         inline=True)
            log_embed.add_field(name="Reason",      value=reason,                           inline=False)
            log_embed.add_field(name="Actioned By", value=interaction.user.mention,         inline=True)
            log_embed.set_thumbnail(url=member.display_avatar.url)
            await log_ch.send(embed=log_embed)

        # Notify the demoted member via DM
        try:
            dm = discord.Embed(
                title="📉 Your rank has changed",
                description=(
                    f"You have been demoted to **{new_name}** "
                    f"in **{interaction.guild.name}**.\n**Reason:** {reason}"
                ),
                colour=0xE74C3C,
            )
            await member.send(embed=dm)
        except discord.Forbidden:
            pass

        await interaction.followup.send(
            f"✅ {member.mention} has been demoted from **{old_name}** to **{new_name}**.",
            ephemeral=True,
        )

    # ── /staffrank ────────────────────────────────────────────────────────────

    @app_commands.command(name="staffrank", description="Check a member's current staff rank")
    @app_commands.describe(member="The member to check (leave blank for yourself)")
    async def staffrank(self, interaction: discord.Interaction, member: discord.Member = None):
        """Shows the staff rank (if any) of the specified member, or yourself."""
        target = member or interaction.user
        rank_index = _get_staff_rank(target)

        embed = discord.Embed(timestamp=datetime.now(timezone.utc))
        embed.set_thumbnail(url=target.display_avatar.url)

        if rank_index is None:
            embed.title = "👤 No Staff Rank"
            embed.description = f"{target.mention} does not hold a staff role."
            embed.colour = 0x95A5A6
        else:
            rank_name = STAFF_RANK_NAMES[STAFF_RANK_ORDER[rank_index]]
            embed.title = "🏅 Staff Rank"
            embed.description = f"{target.mention} is currently **{rank_name}**."
            embed.colour = 0x5865F2

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Error handler ─────────────────────────────────────────────────────────

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Catches permission failures and any unexpected errors in this cog."""
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You don't have the required role.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
    print("Utility cog loaded")