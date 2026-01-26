from .help import setup_help
from .ping import setup_ping
from .moderation import setup_moderation
from .filter import setup_filter
from .about import setup_about
from .music import setup_play

async def register_commands(bot):
    # Await these because bot.add_cog is now a coroutine
    await setup_help(bot)
    await setup_ping(bot)
    await setup_moderation(bot)
    await setup_filter(bot)
    await setup_about(bot)
    await setup_play(bot)
