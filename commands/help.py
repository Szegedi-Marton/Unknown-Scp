import discord
from discord import app_commands
from discord.ext import commands


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.available_commands = [
            'about', 'help', 'ping', 'filter', 'ban',
            'clear', 'kick', 'play', 'stop', 'skip', 'queue'
        ]

    # --- AUTOCOMPLETE LOGIC ---
    async def command_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=cmd, value=cmd)
            for cmd in self.available_commands if current.lower() in cmd.lower()
        ][:25]  # Discord limit is 25 choices

    @app_commands.command(name="help", description="Get help with bot commands")
    @app_commands.autocomplete(command=command_autocomplete)
    @app_commands.describe(command="The specific command you need info on")
    async def help_command(self, interaction: discord.Interaction, command: str = None):
        # Base Help Embed
        if command is None:
            embed = discord.Embed(
                title="Help Menu",
                description="Use `/help [command]` for detailed info.",
                color=discord.Color.dark_red()
            )
            embed.add_field(name="🌐 General", value="`about`, `help`, `ping`")
            embed.add_field(name="🎵 Music", value="`play`, `skip`, `queue`, `stop`")
            embed.add_field(name="🛡️ Admin", value="`filter`, `ban`, `clear`, `kick`")
            return await interaction.response.send_message(embed=embed)

        # Specific Command Help
        embed = discord.Embed(title=f"Help: {command}", color=discord.Color.blue())

        if command == 'ping':
            embed.add_field(
                name="Description",
                value="Checks bot latency or service status with `/ping`."
            )

        elif command == 'filter':
            embed.add_field(
                name="Description",
                value="Manage filtered words using the `/filter` options."
            )

        elif command == 'about':
            embed.add_field(
                name="Description",
                value="Shows bot version and developer info."
            )

        elif command == 'clear':
            embed.add_field(
                name="Description",
                value="Clears a specific amount of messages."
            )

        elif command == 'ban':
            embed.add_field(
                name="Description",
                value="Bans a user from the server using `/ban`."
            )

        elif command == 'kick':
            embed.add_field(
                name="Description",
                value="Kicks a user from the server using `/kick`."
            )

        elif command == 'play':
            embed.add_field(
                name="Description",
                value="Plays music from the web using `/play <song or URL>`."
            )

        elif command == 'skip':
            embed.add_field(
                name="Description",
                value="Skips the currently playing song with `/skip`."
            )

        elif command == 'stop':
            embed.add_field(
                name="Description",
                value="Stops playback and disconnects the bot using `/stop`."
            )

        elif command == 'queue':
            embed.add_field(
                name="Description",
                value="Shows the upcoming songs in the queue with `/queue`."
            )

        else:
            return await interaction.response.send_message(f"No specific help found for `{command}`.", ephemeral=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="iam_lost", description="A quick emergency help guide")
    async def iam_lost(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Somebody called for me...",
            description="If you are lost, here are the essentials:",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="/ping", value="Check latency", inline=False)
        embed.add_field(name="/help", value="The full command list", inline=False)
        embed.add_field(name="/about", value="Bot & Dev info", inline=False)
        embed.set_footer(text="Emergency Help Menu")
        await interaction.response.send_message(embed=embed)


async def setup_help(bot):
    await bot.add_cog(Help(bot))