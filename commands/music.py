import discord
import psutil
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import random
from async_timeout import timeout
from config import spotify_client_id, spotify_client_secret
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# --------------------------
# CONFIGURATION
# --------------------------
ytdl_format_options = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': False,  # Changed to False to allow playlists
    'nocheckcertificate': True,
    'ignoreerrors': True, # Useful for skipping private/deleted videos in a playlist
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'before_options': (
        '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 '
        '-headers "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        '-rw_timeout 10000000 '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\n'
        'Accept: */*\r\n'
        'Connection: keep-alive\r\n"'
    ),
    'options': (
        '-vn '                   # No video
        '-b:a 128k '             # Match standard high-quality bitrate
        '-threads 2 '            # Use 2 threads for decoding
        '-af "loudnorm=I=-16:TP=-1.5:LRA=11" ' # Optional: Normalizes volume (prevents ear-rape)
        '-buffer_size 512k'
    ),
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=spotify_client_id,
    client_secret=spotify_client_secret
))

def get_spotify_tracks(url):
    """Extracts track names from a Spotify playlist URL."""
    playlist_id = url.split('/')[-1].split('?')[0]
    results = sp.playlist_items(playlist_id)
    tracks = []

    for item in results['items']:
        track = item['track']
        # Create a search string: "Artist Name - Song Name"
        tracks.append(f"{track['artists'][0]['name']} - {track['name']}")

    return tracks

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

        # Force a modern user-agent in yt-dlp too
        ytdl.params[
            'user_agent'] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            if 'entries' in data:
                data = data['entries'][0]

            filename = data['url']
            # Pass our updated ffmpeg_options here
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
        except Exception as e:
            print(f"Failed to extract {url}: {e}")
            return None


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
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                async with timeout(300):  # 5 min timeout
                    url = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            # RESOLVE THE URL HERE
            try:
                source = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                if not source:
                    continue  # Skip if the song couldn't be loaded (deleted/private)
            except Exception as e:
                await self._channel.send(f"❌ Error loading song: {e}")
                continue

            self.current = source
            self._guild.voice_client.play(
                source,
                after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set)
            )

            await self._channel.send(f'**Now playing:** {source.title}')
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
        self.titles = {}

    async def cleanup(self, guild):
        try:
            if guild.voice_client:
                await guild.voice_client.disconnect()
        except Exception:
            pass

        try:
            # Cancel the player_loop task before deleting the player
            if self.players[guild.id]:
                self.players[guild.id].task.cancel()
            del self.players[guild.id]
        except (KeyError, AttributeError):
            pass

    def get_player(self, interaction: discord.Interaction):
        try:
            player = self.players[interaction.guild_id]
        except KeyError:
            player = MusicPlayer(interaction, self)
            self.players[interaction.guild_id] = player
        return player

    @app_commands.command(name='play', description='Plays a song or playlist')
    @app_commands.describe(
        search="The song name, URL, playlist (YouTube or Spotify)",
        shuffle="Shuffle the playlist before adding to queue?"
    )
    async def play(self, interaction: discord.Interaction, search: str, shuffle: bool = False):
        await interaction.response.defer()

        if not interaction.user.voice:
            return await interaction.followup.send("❌ You need to be in a voice channel!")

        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect(reconnect=True, timeout=20.0)

        player = self.get_player(interaction)

        # Handle Spotify
        if "spotify.com" in search:
            try:
                track_names = get_spotify_tracks(search)
                track_names = track_names[:25]

                if shuffle:
                    random.shuffle(track_names)  # Shuffle Spotify tracks

                for track in track_names:
                    query = f"ytsearch1:{track}"
                    await player.queue.put(query)
                    self.titles[query] = track

                return await interaction.followup.send(
                    f"✅ Loaded **{len(track_names)}** tracks from Spotify {'(Shuffled) ' if shuffle else ''}into the queue.")
            except Exception as e:
                return await interaction.followup.send(f"❌ Spotify Error: {e}")


        # 1. Determine if the input is a URL or a search query
        is_url = search.startswith(('http://', 'https://'))
        query = search if is_url else f"ytsearch1:{search}"

        ydl_opts = {
            'extract_flat': 'in_playlist' if is_url else False,
            'skip_download': True,
            'yes_playlist': True if is_url else False,
            'playlist_items': '1-25',
            'quiet': True,
            'default_search': 'ytsearch',
        }

        try:
            loop = self.bot.loop or asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                data = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))

            if not data:
                return await interaction.followup.send("❌ Could not find anything.")

            # 2. Handle Search Results
            if not is_url and 'entries' in data:
                if not data['entries']:
                    return await interaction.followup.send("❌ No results found.")
                data = data['entries'][0]

            # 3. Handle Actual Playlists/Mixes (URLs only)
            if 'entries' in data and is_url:
                entries = [e for e in data['entries'] if e is not None and e.get('id')]
                if not entries:
                    return await interaction.followup.send("❌ All videos in this playlist are unavailable.")

                if shuffle:
                    random.shuffle(entries)  # Shuffle YouTube entries

                for entry in entries:
                    video_id = entry.get('id')
                    url = f"https://www.youtube.com/watch?v={video_id}"
                    title = entry.get('title') or "Unknown Title"
                    await player.queue.put(url)
                    self.titles[url] = title

                await interaction.followup.send(
                    f"✅ Loaded **{len(entries)}** tracks from the Mix/Playlist: **{data.get('title')}**")

            # 4. Handle Single Video (or the result from our search)
            else:
                url = data.get('webpage_url') or data.get('url')
                title = data.get('title') or "Unknown Title"
                await player.queue.put(url)
                self.titles[url] = title
                await interaction.followup.send(f"✅ Added **{title}** to queue.")

        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}")


    @app_commands.command(name='skip', description='Skips the current song')
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            return await interaction.response.send_message("🔇 Nothing is playing.", ephemeral=True)

        vc.stop()  # This triggers the 'after' callback in player_loop, which calls self.next.set()
        await interaction.response.send_message("⏭️ **Skipped!**")

    @app_commands.command(name='queue', description='Shows the current music queue')
    async def queue_info(self, interaction: discord.Interaction):
        player = self.get_player(interaction)

        if player.queue.empty():
            return await interaction.response.send_message("The queue is empty.", ephemeral=True)

        # Access the internal list of URLs
        upcoming = list(player.queue._queue)

        # Build the list using our title cache
        queue_list = []
        for i, url in enumerate(upcoming[:10]):  # Show first 10
            title = self.titles.get(url, "Fetching title...")
            queue_list.append(f"**{i + 1}.** {title}")

        fmt = '\n'.join(queue_list)
        await interaction.response.send_message(f"**Upcoming Songs:**\n{fmt}")

    @app_commands.command(name='stop', description='Stops music and disconnects')
    async def stop(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await self.cleanup(interaction.guild)
            await interaction.response.send_message("⏹️ **Stopped and disconnected.**")
        else:
            await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)

    @app_commands.command(name='qclear', description='Clears the entire music queue')
    async def qclear(self, interaction: discord.Interaction):
        player = self.get_player(interaction)

        # Empty the asyncio Queue
        while not player.queue.empty():
            try:
                player.queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        self.titles.clear()  # Clear the title cache too
        await interaction.response.send_message("🧹 **Queue cleared!**")

    @app_commands.command(name='stats', description='Shows bot system performance')
    async def stats(self, interaction: discord.Interaction):
        process = psutil.Process()
        cpu = psutil.cpu_percent()
        ram = process.memory_info().rss / 1024 / 1024
        ping = round(self.bot.latency * 1000)

        embed = discord.Embed(title="🤖 Bot Stats", color=discord.Color.green())
        embed.add_field(name="Network", value=f"Ping: {ping}ms\nStreams: {len(self.players)}")
        embed.add_field(name="System", value=f"CPU: {cpu}%\nRAM: {ram:.1f}MB")
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # If the bot itself is moved or disconnected, we don't need to run this logic
        if member.id == self.bot.user.id:
            return

        # Get the voice client for this guild
        vc = member.guild.voice_client

        # If the bot is not connected to voice, do nothing
        if not vc or not vc.channel:
            return

        # Check if the channel the bot is in is the one that was left
        if before.channel and before.channel.id == vc.channel.id:
            # Count non-bot members
            non_bot_members = [m for m in vc.channel.members if not m.bot]

            # If only the bot is left
            if len(non_bot_members) == 0:
                # Wait 10 seconds
                await asyncio.sleep(10)

                # Check again after 10 seconds to make sure it's still empty
                if vc.channel:
                    non_bot_members = [m for m in vc.channel.members if not m.bot]
                    if len(non_bot_members) == 0:
                        # Optional: Send a message to the music channel
                        # player = self.players.get(member.guild.id)
                        # if player: await player._channel.send("👋 Leaving the channel as it is empty.")

                        await self.cleanup(member.guild)


# --------------------------
# SETUP FUNCTION
# --------------------------
async def setup_play(bot):
    await bot.add_cog(Music(bot))