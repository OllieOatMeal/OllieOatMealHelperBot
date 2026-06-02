import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio

FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"

ytdl = yt_dlp.YoutubeDL({
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "extractor_args": {
        "youtube": {
            "player_client": ["android"]
        }
    }
})


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]

    async def play_next(self, guild):
        queue = self.get_queue(guild.id)

        if not queue:
            return

        voice = guild.voice_client
        if voice is None:
            return

        song = queue.pop(0)

        source = discord.FFmpegPCMAudio(
            song["url"],
            executable=FFMPEG_PATH,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn"
        )

        def after_playing(error):
            future = asyncio.run_coroutine_threadsafe(
                self.play_next(guild),
                self.bot.loop
            )
            try:
                future.result()
            except Exception as e:
                print(e)

        voice.play(source, after=after_playing)

    @app_commands.command(name="play", description="Play music from YouTube")
    async def play(self, interaction: discord.Interaction, query: str):

        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ Join a voice channel first.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        voice = interaction.guild.voice_client

        if voice is None:
            voice = await interaction.user.voice.channel.connect()

        if query.startswith("http"):
            info = ytdl.extract_info(query, download=False)
        else:
            info = ytdl.extract_info(
                f"ytsearch:{query}",
                download=False
            )
            info = info["entries"][0]

        title = info["title"]

        formats = info.get("formats", [])
        audio_formats = [
            f for f in formats
            if f.get("acodec") != "none"
        ]

        if audio_formats:
            url = audio_formats[-1]["url"]
        else:
            url = info["url"]

        queue = self.get_queue(interaction.guild.id)
        queue.append({
            "title": title,
            "url": url
        })

        await interaction.followup.send(
            f"➕ Added to queue: **{title}**"
        )

        if not voice.is_playing():
            await self.play_next(interaction.guild)

    @app_commands.command(name="queue", description="Show current queue")
    async def queue(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)

        if not queue:
            await interaction.response.send_message("Queue is empty.")
            return

        msg = "\n".join(
            f"{i}. {song['title']}"
            for i, song in enumerate(queue, start=1)
        )

        embed = discord.Embed(
            title="🎵 Music Queue",
            description=msg
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="skip", description="Skip current song")
    async def skip(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()

        await interaction.response.send_message("⏭ Skipped.")

    @app_commands.command(name="pause", description="Pause playback")
    async def pause(self, interaction: discord.Interaction):
        voice = interaction.guild.voice_client

        if voice and voice.is_playing():
            voice.pause()

        await interaction.response.send_message("⏸ Paused.")

    @app_commands.command(name="resume", description="Resume playback")
    async def resume(self, interaction: discord.Interaction):
        voice = interaction.guild.voice_client

        if voice and voice.is_paused():
            voice.resume()

        await interaction.response.send_message("▶ Resumed.")

    @app_commands.command(name="stop", description="Stop playback and clear queue")
    async def stop(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        queue.clear()

        voice = interaction.guild.voice_client

        if voice:
            voice.stop()

        await interaction.response.send_message("🛑 Queue cleared.")

    @app_commands.command(name="leave", description="Disconnect from voice")
    async def leave(self, interaction: discord.Interaction):
        voice = interaction.guild.voice_client

        if voice:
            await voice.disconnect()

        await interaction.response.send_message("👋 Disconnected.")


async def setup(bot):
    await bot.add_cog(Music(bot))
