# ══════════════════════════════════════════════════════════════════════════════
# cogs/music.py — YouTube music player with persistent panel embed
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
import os
import random
from collections import deque

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands

FFMPEG_PATH  = os.getenv("FFMPEG_PATH", "ffmpeg")
EMBED_COLOUR = 0x5865F2

YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extractor_args": {"youtube": {"player_client": ["android"]}},
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
    "executable": FFMPEG_PATH,
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)


# ── Guild state ───────────────────────────────────────────────────────────────

class GuildState:
    def __init__(self):
        self.queue: deque[dict] = deque()
        self.current: dict | None = None
        self.volume: float = 1.0
        self.shuffle: bool = False
        self.loop: bool = False
        self.panel_message: discord.Message | None = None
        self.panel_channel_id: int | None = None   # track which channel the panel lives in


# ── Helpers ───────────────────────────────────────────────────────────────────

async def fetch_track(query: str) -> dict | None:
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(query, download=False)
        )
    except Exception as e:
        print(f"[music] yt-dlp error: {e}")
        return None
    if not data:
        return None
    if "entries" in data:
        data = data["entries"][0]
    return {
        "url":       data.get("url") or data.get("webpage_url"),
        "title":     data.get("title", "Unknown title"),
        "uploader":  data.get("uploader") or data.get("channel", "Unknown"),
        "duration":  data.get("duration", 0),
        "webpage":   data.get("webpage_url", ""),
        "thumbnail": data.get("thumbnail", ""),
    }


def fmt_duration(secs) -> str:
    if not secs:
        return "Live"
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def build_embed(state: GuildState) -> discord.Embed:
    vol_pct   = int(state.volume * 100)
    vol_icon  = "🔇" if vol_pct == 0 else ("🔉" if vol_pct < 60 else "🔊")
    footer    = (
        f"Shuffle: {'ON 🔀' if state.shuffle else 'OFF'}  •  "
        f"Loop: {'ON 🔁' if state.loop else 'OFF'}  •  "
        f"{vol_icon} {vol_pct}%"
    )

    if not state.current:
        e = discord.Embed(
            title="🎵 Music Panel",
            description="No track playing.\nUse `/play <song>` to start the queue.",
            colour=EMBED_COLOUR,
        )
        e.set_footer(text=footer)
        return e

    t = state.current
    e = discord.Embed(
        title=t["title"],
        url=t["webpage"] or None,
        description=f"**Uploader:** {t['uploader']}\n**Duration:** {fmt_duration(t['duration'])}",
        colour=EMBED_COLOUR,
    )
    e.set_author(name="▶ Now Playing")
    if t["thumbnail"]:
        e.set_thumbnail(url=t["thumbnail"])

    if state.queue:
        lines = [
            f"`{i}.` {q['title']} — *{q['uploader']}* `{fmt_duration(q['duration'])}`"
            for i, q in enumerate(list(state.queue)[:5], 1)
        ]
        if len(state.queue) > 5:
            lines.append(f"*…and {len(state.queue) - 5} more*")
        e.add_field(
            name=f"Up Next ({len(state.queue)} song{'s' if len(state.queue) != 1 else ''})",
            value="\n".join(lines),
            inline=False,
        )

    e.set_footer(text=footer)
    return e


# ── Button View ───────────────────────────────────────────────────────────────

class MusicView(discord.ui.View):
    def __init__(self, cog: "Music"):
        super().__init__(timeout=None)
        self.cog = cog

    def _state(self, interaction: discord.Interaction) -> GuildState:
        return self.cog.get_state(interaction.guild_id)

    async def _refresh(self, interaction: discord.Interaction):
        state = self._state(interaction)
        embed = build_embed(state)
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"[music] button refresh error: {e}")

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary, custom_id="music:prev", row=0)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        state = self._state(interaction)
        if vc and (vc.is_playing() or vc.is_paused()) and state.current:
            state.queue.appendleft(state.current)
            state.current = None
            vc.stop()
        await self._refresh(interaction)

    @discord.ui.button(emoji="⏯", style=discord.ButtonStyle.primary, custom_id="music:playpause", row=0)
    async def btn_playpause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc:
            if vc.is_paused():
                vc.resume()
            elif vc.is_playing():
                vc.pause()
        await self._refresh(interaction)

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary, custom_id="music:skip", row=0)
    async def btn_skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
        await self._refresh(interaction)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="music:shuffle", row=0)
    async def btn_shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self._state(interaction)
        state.shuffle = not state.shuffle
        button.style = discord.ButtonStyle.success if state.shuffle else discord.ButtonStyle.secondary
        await self._refresh(interaction)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="music:loop", row=0)
    async def btn_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self._state(interaction)
        state.loop = not state.loop
        button.style = discord.ButtonStyle.success if state.loop else discord.ButtonStyle.secondary
        await self._refresh(interaction)

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger, custom_id="music:stop", row=0)
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self._state(interaction)
        state.queue.clear()
        state.current = None
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()
        await self._refresh(interaction)

    @discord.ui.button(label="Vol −", style=discord.ButtonStyle.secondary, custom_id="music:vol_down", row=1)
    async def btn_vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self._state(interaction)
        state.volume = max(0.0, round(state.volume - 0.1, 1))
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = state.volume
        await self._refresh(interaction)

    @discord.ui.button(label="Vol +", style=discord.ButtonStyle.secondary, custom_id="music:vol_up", row=1)
    async def btn_vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self._state(interaction)
        state.volume = min(2.0, round(state.volume + 0.1, 1))
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = state.volume
        await self._refresh(interaction)

    @discord.ui.button(label="Queue", style=discord.ButtonStyle.secondary, custom_id="music:queue", row=1)
    async def btn_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self._state(interaction)
        if not state.queue:
            await interaction.response.send_message("Queue is empty.", ephemeral=True)
            return
        lines = [
            f"`{i}.` **{t['title']}** — {t['uploader']} `{fmt_duration(t['duration'])}`"
            for i, t in enumerate(state.queue, 1)
        ]
        text = "\n".join(lines[:20])
        if len(state.queue) > 20:
            text += f"\n*…and {len(state.queue) - 20} more*"
        embed = discord.Embed(
            title=f"Queue — {len(state.queue)} song{'s' if len(state.queue) != 1 else ''}",
            description=text,
            colour=EMBED_COLOUR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ── Cog ───────────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._states: dict[int, GuildState] = {}

    def get_state(self, guild_id: int) -> GuildState:
        return self._states.setdefault(guild_id, GuildState())

    async def _send_panel(self, channel: discord.TextChannel, state: GuildState):
        """Send a brand-new panel message and store it on state."""
        embed = build_embed(state)
        view  = MusicView(self)
        msg   = await channel.send(embed=embed, view=view)
        state.panel_message    = msg
        state.panel_channel_id = channel.id

    async def _update_panel(self, guild: discord.Guild):
        """Edit the existing panel in-place. Does nothing if there is no panel yet."""
        state = self.get_state(guild.id)
        if not state.panel_message:
            return
        embed = build_embed(state)
        view  = MusicView(self)
        try:
            await state.panel_message.edit(embed=embed, view=view)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            state.panel_message    = None
            state.panel_channel_id = None

    async def play_next(self, guild: discord.Guild):
        state = self.get_state(guild.id)
        vc    = guild.voice_client
        if vc is None:
            return

        if state.loop and state.current:
            state.queue.appendleft(state.current)

        if not state.queue:
            state.current = None
            await self._update_panel(guild)
            return

        if state.shuffle and len(state.queue) > 1:
            idx   = random.randrange(len(state.queue))
            lst   = list(state.queue)
            track = lst.pop(idx)
            state.queue = deque(lst)
        else:
            track = state.queue.popleft()

        state.current = track

        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTS),
            volume=state.volume,
        )

        def after_playing(error):
            if error:
                print(f"[music] playback error: {error}")
            asyncio.run_coroutine_threadsafe(self.play_next(guild), self.bot.loop)

        vc.play(source, after=after_playing)
        await self._update_panel(guild)

    # ── /play ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Play a song from YouTube (search term or URL)")
    @app_commands.describe(query="Song name or YouTube URL")
    async def play(self, interaction: discord.Interaction, query: str):
        print(f"[music] /play called by {interaction.user} query={query!r}")
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ Join a voice channel first.", ephemeral=True
            )
            return

        try:
            await interaction.response.defer(ephemeral=True)
            print("[music] /play deferred ok")
        except Exception as e:
            print(f"[music] /play defer FAILED: {e}")
            return

        try:
            voice_channel = interaction.user.voice.channel
            vc = interaction.guild.voice_client
            if vc is None:
                vc = await voice_channel.connect()
            elif vc.channel != voice_channel:
                await vc.move_to(voice_channel)
            print(f"[music] voice connected to {voice_channel}")
        except Exception as e:
            print(f"[music] voice connect FAILED: {e}")
            await interaction.followup.send(f"❌ Could not join voice: {e}", ephemeral=True)
            return

        try:
            track = await fetch_track(query)
            print(f"[music] fetch_track returned: {track['title'] if track else None}")
        except Exception as e:
            print(f"[music] fetch_track FAILED: {e}")
            await interaction.followup.send(f"❌ Track fetch error: {e}", ephemeral=True)
            return

        if not track:
            await interaction.followup.send("❌ Could not find that track.", ephemeral=True)
            return

        state = self.get_state(interaction.guild_id)
        state.queue.append(track)

        already_playing = vc.is_playing() or vc.is_paused()

        if not already_playing:
            try:
                await self.play_next(interaction.guild)
                print("[music] play_next ok")
            except Exception as e:
                print(f"[music] play_next FAILED: {e}")
                await interaction.followup.send(f"❌ Playback error: {e}", ephemeral=True)
                return

        try:
            channel = interaction.channel
            await self._send_panel(channel, state)
            print(f"[music] panel sent to #{channel}")
        except Exception as e:
            print(f"[music] _send_panel FAILED: {e}")

        msg = f"✅ Added to queue: **{track['title']}**" if already_playing else f"▶ Now playing **{track['title']}**"
        try:
            await interaction.followup.send(msg, ephemeral=True)
            print("[music] followup sent ok")
        except Exception as e:
            print(f"[music] followup FAILED: {e}")

    # ── /panel ────────────────────────────────────────────────────────────────

    @app_commands.command(name="panel", description="Re-post the music panel in this channel")
    async def panel(self, interaction: discord.Interaction):
        print(f"[music] /panel called by {interaction.user}")
        try:
            await interaction.response.defer(ephemeral=True)
            print("[music] /panel deferred ok")
        except Exception as e:
            print(f"[music] /panel defer FAILED: {e}")
            return

        state = self.get_state(interaction.guild_id)
        state.panel_message    = None
        state.panel_channel_id = None

        try:
            channel = interaction.channel
            print(f"[music] sending panel to channel: {channel} (type={type(channel).__name__})")
            await self._send_panel(channel, state)
            print("[music] panel send ok")
        except Exception as e:
            print(f"[music] _send_panel FAILED: {e}")
            await interaction.followup.send(f"❌ Panel error: {e}", ephemeral=True)
            return

        try:
            await interaction.followup.send("🎵 Panel posted!", ephemeral=True)
        except Exception as e:
            print(f"[music] /panel followup FAILED: {e}")

    # ── /stop ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="stop", description="Stop playback and leave voice")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        state = self.get_state(interaction.guild_id)
        state.queue.clear()
        state.current = None
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()
        await self._update_panel(interaction.guild)
        await interaction.followup.send("⏹ Stopped and disconnected.", ephemeral=True)

    # ── /queue ────────────────────────────────────────────────────────────────

    @app_commands.command(name="queue", description="Show the current queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        if not state.queue and not state.current:
            await interaction.response.send_message("Queue is empty.", ephemeral=True)
            return
        lines = []
        if state.current:
            lines.append(
                f"**▶ {state.current['title']}** — {state.current['uploader']} "
                f"`{fmt_duration(state.current['duration'])}`"
            )
        for i, t in enumerate(list(state.queue)[:20], 1):
            lines.append(f"`{i}.` {t['title']} — {t['uploader']} `{fmt_duration(t['duration'])}`")
        if len(state.queue) > 20:
            lines.append(f"*…and {len(state.queue) - 20} more*")
        embed = discord.Embed(
            title=f"Queue — {len(state.queue)} song{'s' if len(state.queue) != 1 else ''} queued",
            description="\n".join(lines),
            colour=EMBED_COLOUR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /skip ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="skip", description="Skip the current track")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭ Skipped.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    # ── /pause ────────────────────────────────────────────────────────────────

    @app_commands.command(name="pause", description="Pause playback")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸ Paused.", ephemeral=True)
            await self._update_panel(interaction.guild)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    # ── /resume ───────────────────────────────────────────────────────────────

    @app_commands.command(name="resume", description="Resume playback")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶ Resumed.", ephemeral=True)
            await self._update_panel(interaction.guild)
        else:
            await interaction.response.send_message("Not paused.", ephemeral=True)

    # ── /volume ───────────────────────────────────────────────────────────────

    @app_commands.command(name="volume", description="Set volume (0–200)")
    @app_commands.describe(level="Volume level from 0 to 200")
    async def volume(self, interaction: discord.Interaction, level: app_commands.Range[int, 0, 200]):
        state = self.get_state(interaction.guild_id)
        state.volume = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = state.volume
        await interaction.response.send_message(f"🔊 Volume set to **{level}%**.", ephemeral=True)
        await self._update_panel(interaction.guild)

    # ── /shuffle ──────────────────────────────────────────────────────────────

    @app_commands.command(name="shuffle", description="Toggle shuffle mode")
    async def shuffle_cmd(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        state.shuffle = not state.shuffle
        await interaction.response.send_message(
            f"Shuffle **{'on 🔀' if state.shuffle else 'off'}**.", ephemeral=True
        )
        await self._update_panel(interaction.guild)

    # ── /loop ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="loop", description="Toggle loop mode")
    async def loop_cmd(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)
        state.loop = not state.loop
        await interaction.response.send_message(
            f"Loop **{'on 🔁' if state.loop else 'off'}**.", ephemeral=True
        )
        await self._update_panel(interaction.guild)

    # ── /leave ────────────────────────────────────────────────────────────────

    @app_commands.command(name="leave", description="Leave voice channel")
    async def leave(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect()
            await interaction.response.send_message("👋 Left voice channel.", ephemeral=True)
        else:
            await interaction.response.send_message("Not in a voice channel.", ephemeral=True)


# ── Setup ─────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    cog = Music(bot)
    await bot.add_cog(cog)
    print("Music cog loaded")
    for cmd in cog.walk_app_commands():
        print(f"  - /{cmd.name}")