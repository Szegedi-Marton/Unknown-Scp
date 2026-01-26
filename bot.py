import discord
from discord.ext import commands
from config import DISCORD_TOKEN
from events import register_events
from modules.filter_module import load_filtered_words
from commands import register_commands



class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        """
        This is called once when the bot starts up, before it connects to Discord.
        Ideal for registering commands and syncing slash commands.
        """
        # Load data
        load_filtered_words()

        await register_commands(self)
        register_events(self)
        await self.tree.sync()

        @bot.command()
        @commands.is_owner()
        async def sync(ctx):
            await bot.tree.sync()
            await ctx.send("✅ Slash commands synced globally!")


# Initialize the bot class
bot = MyBot()
bot.run(DISCORD_TOKEN)