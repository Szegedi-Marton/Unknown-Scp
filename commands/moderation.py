import discord
from discord import app_commands
from discord.ext import commands


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- KICK COMMAND ---
    @app_commands.command(name="kick", description="Kicks a member from the server")
    @app_commands.describe(member="The member to kick", reason="The reason for the kick")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        if member.id == interaction.client.user.id:
            return await interaction.response.send_message("I cannot kick myself!", ephemeral=True)

        try:
            await member.kick(reason=reason)
            await interaction.response.send_message(
                f'✅ Kicked **{member.display_name}** for: {reason or "No reason provided"}')
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to kick this user (they might have a higher role).", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Kicking failed: {e}", ephemeral=True)

    # --- BAN COMMAND ---
    @app_commands.command(name="ban", description="Bans a member from the server")
    @app_commands.describe(member="The member to ban", reason="The reason for the ban")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = None):
        if member.id == interaction.client.user.id:
            return await interaction.response.send_message("I cannot ban myself!", ephemeral=True)

        try:
            await member.ban(reason=reason)
            await interaction.response.send_message(
                f'🔨 Banned **{member.display_name}** for: {reason or "No reason provided"}')
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to ban this user.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Banning failed: {e}", ephemeral=True)

    # --- CLEAR COMMAND ---
    @app_commands.command(name="clear", description="Deletes a specific amount of messages")
    @app_commands.describe(amount="How many messages to delete")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if amount < 1:
            return await interaction.response.send_message("Please specify a number greater than 0.", ephemeral=True)

        # Defer because purging can take a moment
        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await interaction.channel.purge(limit=amount)
            await interaction.followup.send(f'🗑️ Deleted **{len(deleted)}** messages.')
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to manage messages.")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to delete: {e}")


async def setup_moderation(bot):
    await bot.add_cog(Moderation(bot))