import discord
from modules.filter_module import filtered_words
from discord.ext import tasks


def register_events(bot):
    @bot.event
    async def on_ready():
        await update_status()
        await bot.tree.sync()
        print(f'Logged in as {bot.user}')


    @tasks.loop(hours=1)
    async def update_status():
        server_count = len(bot.guilds)
        activity = discord.Streaming(
            name=f"Connected across {server_count:,} servers 🌍",
            url="https://www.twitch.tv/discord"
        )
        await bot.change_presence(activity=activity)


    @bot.event
    async def on_guild_join(guild):
        filtered_words[str(guild.id)] = []

        owner = guild.owner
        embed = discord.Embed(
            title="Thanks for choosing me~",
            description="*Unlock the potential* with **UnknownScp**",
            color=discord.Color.dark_purple()
        )
        embed.add_field(name="Getting started", value="Try out my /help command", inline=False)
        embed.set_footer(text="This message should be sent when you added the bot")

        if owner.dm_channel is None:
            await owner.create_dm()
        await owner.dm_channel.send(embed=embed)

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return

        if message.guild:
            guild_id = str(message.guild.id)

            # Skip filtering if it's a command (starts with prefix)
            # You might want to change this if you want to filter bad words INSIDE commands
            is_command = message.content.startswith(bot.command_prefix)

            if guild_id in filtered_words and not is_command:
                # Check for bad words
                for word in filtered_words[guild_id]:
                    if word in message.content.lower():
                        try:
                            await message.delete()
                            # Send warning and auto-delete it after 5 seconds
                            await message.channel.send(
                                f"{message.author.mention}, that language is not allowed here.",
                                delete_after=5
                            )
                            return  # Stop processing (don't try to run commands)
                        except discord.Forbidden:
                            print(f"Missing permissions to delete message in {message.guild.name}")
                            return

        # 3. Handle DM Messages
        if isinstance(message.channel, discord.DMChannel):
                embed = discord.Embed(
                    title="Oh-Oh you shouldn't be here~",
                    description="Use !help on a server channel.",
                    color=discord.Color.dark_purple()
                )
                await message.channel.send(embed=embed)
                return

        await bot.process_commands(message)
