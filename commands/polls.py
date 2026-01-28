import discord
from discord import app_commands
from discord.ext import commands


class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="poll", description="Create a simple reaction poll")
    @app_commands.describe(question="What are we voting on?", options="Separated by commas (e.g. Valorant, Minecraft)")
    async def poll(self, interaction: discord.Interaction, question: str, options: str):
        # Split the options into a list
        option_list = [opt.strip() for opt in options.split(',')]
        if len(option_list) > 10:
            return await interaction.response.send_message("❌ Keep it to 10 options or fewer!", ephemeral=True)

        # Use a set of emojis for the options
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        description = ""
        for i, option in enumerate(option_list):
            description += f"{emojis[i]} {option}\n\n"

        embed = discord.Embed(title=f"📊 {question}", description=description, color=discord.Color.blue())
        embed.set_footer(text=f"Poll created by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

        # Add reactions to the message we just sent
        message = await interaction.original_response()
        for i in range(len(option_list)):
            await message.add_reaction(emojis[i])

async def setup_polls(bot):
    # Add the Cog to the bot (the bot then adds it to the tree)
    await bot.add_cog(Polls(bot))