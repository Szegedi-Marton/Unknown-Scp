import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import re


class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="remindme", description="Set a personal reminder")
    async def remindme(self, interaction: discord.Interaction, time: str, task: str):
        # Basic regex to get numbers and time units (e.g. 10m, 2h)
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        match = re.match(r"(\d+)([smhd])", time.lower())

        if not match:
            return await interaction.response.send_message("❌ Use formats like `10m`, `2h`, or `30s`!", ephemeral=True)

        seconds = int(match.group(1)) * units[match.group(2)]
        await interaction.response.send_message(f"✅ Reminder set to **{task}** in {time}.")

        await asyncio.sleep(seconds)
        await interaction.user.send(f"🔔 **Reminder:** {task}")

async def setup_reminder(bot):
    # Add the Cog to the bot (the bot then adds it to the tree)
    await bot.add_cog(Reminder(bot))