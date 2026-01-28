import discord
from discord import app_commands
from discord.ext import commands
import asyncio

class CountDwn(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="countdown", description="Start a live countdown (max 60 seconds)")
    async def countdown(self, interaction: discord.Interaction, seconds: int):
        if seconds > 60:
            return await interaction.response.send_message("❌ Please keep it under 60 seconds for live updates.",
                                                           ephemeral=True)

        await interaction.response.send_message(f"⏳ **Countdown:** {seconds}...")
        message = await interaction.original_response()

        for i in range(seconds - 1, -1, -1):
            await asyncio.sleep(1)
            await message.edit(content=f"⏳ **Countdown:** {i}...")

        await message.edit(content="**Time's up!**")


async def setup_countDwn(bot):
    # Add the Cog to the bot (the bot then adds it to the tree)
    await bot.add_cog(CountDwn(bot))