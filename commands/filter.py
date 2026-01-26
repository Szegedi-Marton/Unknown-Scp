import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from modules.filter_module import filtered_words, save_filtered_words

class Filter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Slash command with choices for Add/Delete
    @app_commands.command(name="filter", description="Manage the word filter for this server")
    @app_commands.describe(
        action="Choose to add, delete, or view the filter",
        word="The word to add or remove (leave empty to view list)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Delete", value="delete"),
        app_commands.Choice(name="View List", value="view")
    ])
    @app_commands.checks.has_permissions(manage_messages=True)
    async def filter_command(self, interaction: discord.Interaction, action: str, word: str = None):
        guild_id = str(interaction.guild.id)

        # Ensure the guild has an entry
        if guild_id not in filtered_words:
            filtered_words[guild_id] = []

        # --- VIEW LIST ---
        if action == "view":
            words = filtered_words[guild_id]
            if words:
                await interaction.response.send_message(
                    f"Filtered words in **{interaction.guild.name}**:\n||`{', '.join(words)}`||",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("No filtered words in the list.", ephemeral=True)
            return

        # --- VALIDATE INPUT FOR ADD/DELETE ---
        if word is None:
            await interaction.response.send_message("You must specify a word to add or delete.", ephemeral=True)
            return

        word = word.lower()

        # --- ADD WORD ---
        if action == "add":
            if word in filtered_words[guild_id]:
                await interaction.response.send_message(f"||`{word}`|| is already filtered.", ephemeral=True)
            else:
                filtered_words[guild_id].append(word)
                save_filtered_words()
                await interaction.response.send_message(f"Added ||`{word}`|| to the filter list.")

        # --- DELETE WORD ---
        elif action == "delete":
            if word in filtered_words[guild_id]:
                filtered_words[guild_id].remove(word)
                save_filtered_words()
                await interaction.response.send_message(f"Removed ||`{word}`|| from the filter list.")
            else:
                await interaction.response.send_message(f"||`{word}`|| is not in the list.", ephemeral=True)

        # Note: Purging messages is usually not done with slash commands
        # because interactions are handled differently than text commands.

async def setup_filter(bot):
    await bot.add_cog(Filter(bot))