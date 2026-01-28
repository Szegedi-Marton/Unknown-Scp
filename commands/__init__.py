from .help import setup_help
from .ping import setup_ping
from .moderation import setup_moderation
from .filter import setup_filter
from .about import setup_about
from .music import setup_play
from .polls import setup_polls
from .countdown import setup_countDwn
from .reminder import setup_reminder
from .user_info import setup_userInf


async def register_commands(bot):
    # Await these because bot.add_cog is now a coroutine
    await setup_help(bot)
    await setup_ping(bot)
    await setup_moderation(bot)
    await setup_filter(bot)
    await setup_about(bot)
    await setup_play(bot)
    await setup_reminder(bot)
    await setup_countDwn(bot)
    await setup_polls(bot)
    await setup_userInf(bot)
