"""
Telegram bot entry point.
"""

import asyncio
import logging

from app.core.bot_setup import bot, dp
from app.core.infrastructure import make_scheduler, shutdown, startup
from app.services.movie_api import movie_service
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await startup()

    # Scheduler: warm cache on start, then every 24 h
    scheduler = make_scheduler()
    scheduler.add_job(movie_service.warm_cache, "interval", hours=24, id="warm_cache")
    scheduler.start()
    asyncio.create_task(movie_service.warm_cache(), name="initial_cache_warm")

    try:
        if settings.WEBHOOK_URL:
            # Webhook mode
            from aiogram.webhook.aiohttp_server import (
                SimpleRequestHandler,
                setup_application,
            )
            from aiohttp import web

            webhook_url = f"{settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}"
            await bot.set_webhook(webhook_url, drop_pending_updates=True)
            logger.info("Webhook registered %s", webhook_url)

            app = web.Application()
            SimpleRequestHandler(dispatcher=dp, bot=bot).register(
                app, path=settings.WEBHOOK_PATH
            )
            setup_application(app, dp, bot=bot)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, settings.HOST, settings.BOT_PORT)
            await site.start()
            logger.info(
                "Bot webhook server listening on %s:%s", 
                settings.HOST, settings.BOT_PORT
            )

            # Run until interrupted
            await asyncio.Event().wait()

            await runner.cleanup()
            await bot.delete_webhook()

        else:
            # Polling mode
            logger.info("Starting long-polling...")
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
            )

    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await shutdown()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
