import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
from async_timeout import timeout

# --------------------------
# CONFIGURATION
# --------------------------
ytdl_format_options = {
    'cookiefile': 'youtube_cookies.txt',
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


# --------------------------
# YOUTUBE SOURCE HANDLER
# --------------------------
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url']

        # NEW: Advanced ffmpeg options to prevent -10054
        # We force a real browser User-Agent and set a larger buffer
        ffmpeg_final_options = ffmpeg_options.copy()
        ffmpeg_final_options['before_options'] = (
            '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 '
            '-headers "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" '
        )

        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_final_options), data=data)


# --------------------------
# QUEUE MANAGER (PER SERVER)
# --------------------------
class MusicPlayer:
    """A class assigned to each guild to manage its specific queue."""

    def __init__(self, interaction: discord.Interaction, cog):
        # Interactions use .client instead of .bot
        self.bot = interaction.client
        self._guild = interaction.guild
        self._channel = interaction.channel
        self._cog = cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.current = None  # Currently playing song
        # Use the client's loop
        self.task = self.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """The main loop that plays songs from the queue."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                # Wait 5 minutes for a song, otherwise disconnect
                async with timeout(300):
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            self.current = source
            self._guild.voice_client.play(
                source,
                after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set)
            )

            await self._channel.send(f'**Now playing:** {source.title}')

            # Wait for the song to finish (triggered by 'after' callback)
            await self.next.wait()

            # Cleanup
            self.current = None
            source.cleanup()

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))


# --------------------------
# MAIN MUSIC COMMANDS
# --------------------------
class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
        try:
            if guild.voice_client:
                await guild.voice_client.disconnect()
        except Exception:
            pass

        try:
            del self.players[guild.id]
        except KeyError:
            pass

    def get_player(self, interaction: discord.Interaction):
        """Helper to get or create a player for a guild."""
        try:
            player = self.players[interaction.guild_id]
        except KeyError:
            player = MusicPlayer(interaction, self)  # Pass self as the cog reference
            self.players[interaction.guild_id] = player
        return player

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Check if the bot is in a voice channel in this guild
        voice_client = member.guild.voice_client
        if not voice_client:
            return

        # Check if the channel the bot is in has changed
        # We only care if people left the bot's channel
        if before.channel and before.channel.id == voice_client.channel.id:
            # Check if there are any non-bot members left
            non_bot_members = [m for m in voice_client.channel.members if not m.bot]

            if len(non_bot_members) == 0:
                # Wait 30 seconds
                await asyncio.sleep(30)

                # Check again after 30 seconds to see if someone rejoined
                # and if the bot is still connected
                if voice_client.channel:
                    non_bot_members = [m for m in voice_client.channel.members if not m.bot]
                    if len(non_bot_members) == 0:
                        await self.cleanup(member.guild)

    @app_commands.command(name='play', description='Plays a song from YouTube')
    @app_commands.describe(search="The song name or URL to play")
    async def play(self, interaction: discord.Interaction, search: str):
        await interaction.response.defer()

        if not interaction.user.voice:
            return await interaction.followup.send("❌ You need to be in a voice channel!")

        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect(reconnect=True, timeout=20.0)

        player = self.get_player(interaction)

        try:
            source = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True)
            await player.queue.put(source)
            await interaction.followup.send(f'✅ **Added to queue:** {source.title}')
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {e}")

    @app_commands.command(name='skip', description='Skips the current song')
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client

        if not vc or not vc.is_playing():
            return await interaction.response.send_message("🔇 Nothing is playing right now.", ephemeral=True)

        vc.stop()
        await interaction.response.send_message("⏭️ **Skipped!**")

    @app_commands.command(name='queue', description='Shows the current music queue')
    async def queue_info(self, interaction: discord.Interaction):
        player = self.get_player(interaction)

        if player.queue.empty():
            return await interaction.response.send_message("📋 The queue is empty.", ephemeral=True)

        # Accessing internal queue for viewing
        upcoming = list(player.queue._queue)
        fmt = '\n'.join([f'**{i + 1}.** {song.title}' for i, song in enumerate(upcoming[:5])])

        await interaction.response.send_message(f"**Upcoming Songs:**\n{fmt}")

    @app_commands.command(name='stop', description='Stops music and disconnects the bot')
    async def stop(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await self.cleanup(interaction.guild)
            await interaction.response.send_message("⏹️ **Disconnected and cleared the queue.**")
        else:
            await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)


# --------------------------
# SETUP FUNCTION
# --------------------------
async def setup_play(bot):
    await bot.add_cog(Music(bot))