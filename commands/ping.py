import discord
from discord import app_commands
from discord.ext import commands
import os
from utils.downdetector import fetch_status_and_chart


class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check bot latency or a specific service status")
    @app_commands.describe(service="The service to check on Downdetector (optional)")
    async def ping_command(self, interaction: discord.Interaction, service: str = None):
        # Case 1: Simple Latency Check
        if service is None:
            latency = self.bot.latency * 1000
            return await interaction.response.send_message(f"📡 **Bot Latency:** {latency:.0f} ms")

        # Case 2: Service Status Check
        # We need to defer because scraping takes time
        await interaction.response.defer(thinking=True)

        try:
            status, chart_path = await fetch_status_and_chart(service)

            if status and chart_path:
                file = discord.File(chart_path, filename="chart.png")
                await interaction.followup.send(
                    content=f"🔍 **Status for {service.capitalize()}:**\n{status}\n*Source: Downdetector*",
                    file=file
                )

                # Cleanup the chart image
                if os.path.exists(chart_path):
                    os.remove(chart_path)
            else:
                await interaction.followup.send(
                    f"❌ Could not retrieve status for `{service}`. Verify the domain slug on Downdetector."
                )

        except Exception as e:
            print(f"Ping Scraper Error: {e}")
            await interaction.followup.send("⚠️ An error occurred while trying to reach Downdetector.")


async def setup_ping(bot):
    await bot.add_cog(Ping(bot))