import discord
from discord import app_commands
from discord.ext import commands
from modules.lyrics_module import lyrics_enabled, save_lyrics_settings


class Lyrics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="lyrics",
        description="Toggle synced lyrics while music is playing"
    )
    async def lyrics(self, interaction: discord.Interaction):

        guild = interaction.guild

        # Toggle lyrics for this guild
        current = lyrics_enabled.get(str(guild.id), False)
        lyrics_enabled[str(guild.id)] = not current
        save_lyrics_settings()

        state = "enabled" if lyrics_enabled[str(guild.id)] else "disabled"

        embed = discord.Embed(
            title="Lyrics Toggle",
            description=f"Lyrics have been **{state}** for this server.",
            color=discord.Color.purple()
        )

        await interaction.response.send_message(embed=embed)


async def setup_lyrics(bot):
    await bot.add_cog(Lyrics(bot))
