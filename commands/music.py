import psutil
from discord.ext import commands
from discord import app_commands
import yt_dlp
import random
from async_timeout import timeout
import discord
from config import spotify_client_id, spotify_client_secret, sp_dc
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import asyncio
from syrics.api import Spotify

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
        '-rw_timeout 10000000 '
        '-probesize 32k '
        '-analyzeduration 0 ' # Added space here
        '-headers "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\nAccept: */*\r\nConnection: keep-alive\r\n"'
    ),
    'options': (
        '-vn '
        '-b:a 128k '
        '-threads 1 '
        '-af "loudnorm=I=-16:TP=-1.5:LRA=11" ' 
        '-buffer_size 2M'
    ),
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# Initialize Spotify client for Metadata (Spotipy)
# Change 'sp' to 'spotify_meta'
spotify_meta = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=spotify_client_id,
    client_secret=spotify_client_secret
))
# Initialize Spotify client for Lyrics (Syrics)
# Change 'sp' to 'spotify_lyrics'
spotify_lyrics = Spotify(sp_dc)


def get_spotify_tracks(url):
    """Handles both single tracks and playlists."""
    if 'track' in url:
        track_id = url.split('/')[-1].split('?')[0]
        # Use spotify_meta here
        track = spotify_meta.track(track_id)
        return [{'title': f"{track['artists'][0]['name']} - {track['name']}", 'spotify_id': track_id}]

    elif 'playlist' in url:
        playlist_id = url.split('/')[-1].split('?')[0]
        # Use spotify_meta here
        results = spotify_meta.playlist_items(playlist_id)
        tracks = []
        for item in results['items']:
            if item['track']:
                t = item['track']
                tracks.append({'title': f"{t['artists'][0]['name']} - {t['name']}", 'spotify_id': t['id']})
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

        spotify_id = None
        if isinstance(url, dict):
            spotify_id = url.get('spotify_id')
            # Search query for Spotify tracks
            search_query = f"ytsearch5:{url.get('title')} topic lyrics"
        else:
            # Direct YouTube URL
            search_query = url

        with yt_dlp.YoutubeDL(ytdl_format_options) as ydl:
            try:
                data = await loop.run_in_executor(None, lambda: ydl.extract_info(search_query, download=not stream))

                if not data:
                    print(f"❌ No data found for: {search_query}")
                    return None

                # --- NEW LOGIC: Check if it's a Search or a Direct Link ---
                if 'entries' in data:
                    # It's a search result (like from Spotify tracks)
                    if not data['entries']:
                        print(f"❌ No YouTube results for: {search_query}")
                        return None

                    # --- SMART SELECTION LOGIC ---
                    entries = data['entries']
                    best_entry = entries[0]

                    for entry in entries:
                        if entry is None: continue
                        title = entry.get('title', '').lower()
                        uploader = entry.get('uploader', '').lower()

                        if "- topic" in uploader:
                            best_entry = entry
                            break
                        elif "lyrics" in title or "lyric video" in title:
                            best_entry = entry

                    data = best_entry
                # else:
                #   If 'entries' is NOT in data, it's a direct URL.
                #   We just keep 'data' as it is.

                # Re-attach the spotify_id so the player_loop can see it!
                if spotify_id:
                    data['spotify_id'] = spotify_id

                filename = data['url']
                return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

            except Exception as e:
                print(f"❌ YTDL Extraction Error: {e}")
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
                # 5 minute idle timeout
                async with timeout(300):
                    url = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            # RETRY LOGIC for 403/Network Errors
            source = None
            for attempt in range(2):
                try:
                    # We pass stream=True to ensure we get a fresh URL right now
                    source = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                    if source:
                        break
                except Exception as e:
                    if attempt == 0:
                        continue  # Try one more time
                    await self._channel.send(f"❌ Error loading song: {e}")

            if not source:
                continue

            self.current = source

            # Ensure the voice client still exists
            if not self._guild.voice_client:
                return self.destroy(self._guild)

            # 1. Capture the exact start time (in seconds)
            start_time = asyncio.get_event_loop().time()

            self._guild.voice_client.play(
                source,
                after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set)
            )

            # --- TRIGGER SYNCED LYRICS HERE ---
            # Get the Spotify ID we stored in the source data
            track_id = source.data.get('spotify_id')

            # Only start if the toggle is ON and we have a Spotify ID
            from modules.lyrics_module import lyrics_enabled
            if lyrics_enabled.get(str(self._guild.id)) and track_id:
                # We don't 'await' this; we create it as a background task
                self.bot.loop.create_task(self.sync_lyrics_task(self._channel, track_id, start_time))
            # ----------------------------------

            await self._channel.send(f'🎶 **Now playing:** {source.title}')
            await self.next.wait()



    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))

    async def sync_lyrics_task(self, ctx, track_id, start_time):
        try:
            # Fetch lines from the syrics/Spotify API
            data = spotify_lyrics.get_lyrics(track_id)
            if not data or 'lyrics' not in data:
                return

            lines = data['lyrics']['lines']
            message = await ctx.send("⌛ **Syncing lyrics...**")

            # Stay in loop while music is playing
            while self._guild.voice_client and self._guild.voice_client.is_playing():
                # 1. Calculate how far into the song we are (ms)
                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000

                # 2. Find the index of the line currently being sung
                current_line_index = 0
                for i, line in enumerate(lines):
                    if int(line['startTimeMs']) <= elapsed:
                        current_line_index = i
                    else:
                        break

                # 3. Create the "Scrolling" display (3 lines)
                display = ""
                for i in range(current_line_index - 1, current_line_index + 2):
                    if 0 <= i < len(lines):
                        if i == current_line_index:
                            display += f"🎙️ **{lines[i]['words']}**\n"  # Current line
                        else:
                            display += f" {lines[i]['words']} \n"  # Surrounding lines

                # 4. Update the Embed
                embed = discord.Embed(
                    title="🎶 Synced Lyrics",
                    description=display if display else "...",
                    color=0x1DB954  # Spotify Green
                )

                await message.edit(content=None, embed=embed)

                # Wait 2 seconds to avoid Discord rate limits (don't go lower!)
                await asyncio.sleep(2)

            # Cleanup: Delete lyrics when song ends
            await message.delete()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Lyrics Error: {e}")

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

                # Change this part in your /play command
                for track_data in track_names:
                    # If get_spotify_tracks returns a list of dicts:
                    # track_data = {'title': 'Song Name', 'spotify_id': '123'}
                    await player.queue.put(track_data)
                    # Use the title for the cache
                    self.titles[track_data['title']] = track_data['title']

                return await interaction.followup.send(
                    f"✅ Loaded **{len(track_names)}** tracks from Spotify {'(Shuffled) ' if shuffle else ''}into the queue.")
            except Exception as e:
                return await interaction.followup.send(f"❌ Spotify Error: {e}")


        # 1. Determine if the input is a URL or a search query
        is_url = search.startswith(('http://', 'https://'))
        if not is_url:
            query = f"ytsearch1:{search} topic"
        else:
            query = search

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

        # Access the internal list of items (URLs or Spotify Dicts)
        upcoming = list(player.queue._queue)

        queue_list = []
        for i, item in enumerate(upcoming[:10]):  # Show first 10
            # --- FIX LOGIC HERE ---
            if isinstance(item, dict):
                # If it's a Spotify dict, just grab the title we saved
                title = item.get('title', 'Unknown Spotify Track')
            else:
                # If it's a YouTube URL string, look it up in the cache
                title = self.titles.get(item, "Fetching title...")

            queue_list.append(f"**{i + 1}.** {title}")

        fmt = '\n'.join(queue_list)

        embed = discord.Embed(
            title="🎶 Current Queue",
            description=fmt,
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='stop', description='Stops music and disconnects')
    async def stop(self, interaction: discord.Interaction):
        player = self.get_player(interaction)  # Get the player instance
        if interaction.guild.voice_client:
            player.current = None  # Reset the current song
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