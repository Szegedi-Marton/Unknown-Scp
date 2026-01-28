import discord
from discord import app_commands
from discord.ext import commands


class UserInf(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="userinfo", description="Shows detailed info about a member")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        roles = [role.mention for role in member.roles[1:]]  # Skip @everyone

        embed = discord.Embed(title=f"User Info - {member}", color=member.color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Joined Discord", value=member.created_at.strftime("%d %b %Y"), inline=True)
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%d %b %Y"), inline=True)
        embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles) if roles else "None", inline=False)

        await interaction.response.send_message(embed=embed)

async def setup_userInf(bot):
    # Add the Cog to the bot (the bot then adds it to the tree)
    await bot.add_cog(UserInf(bot))