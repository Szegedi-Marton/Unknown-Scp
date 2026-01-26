import discord
from discord import app_commands
from discord.ext import commands


class About(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # FIX: Use app_commands.command instead of commands.command
    @app_commands.command(name="about", description="View information about the bot and developer")
    async def about(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="This is the about page",
            description="If you are enjoying the bot please give us a review",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="Note", value="this bot is far from perfect...", inline=False)
        embed.add_field(name="Current version", value="0.7v", inline=False)
        embed.add_field(name="About the developer", value="Reach me at deluxplayz. DMs open.", inline=False)

        # Now this will work because 'interaction' is correctly passed
        await interaction.response.send_message(embed=embed)

async def setup_about(bot):
    # Add the Cog to the bot (the bot then adds it to the tree)
    await bot.add_cog(About(bot))