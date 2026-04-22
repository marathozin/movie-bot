import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from infrastructure.api.kinopoisk import kinopoisk_client
from infrastructure.cache.redis_client import redis_client

# from infrastructure.db.database import init_db


logger = logging.getLogger(__name__)


async def startup() -> None:
    """Connect infrastructure clients and initialise the DB schema."""
    await redis_client.connect()
    await kinopoisk_client.connect()
    # await init_db()
    logger.info("Infrastructure ready.")


async def shutdown() -> None:
    """Disconnect infrastructure clients."""
    await redis_client.disconnect()
    await kinopoisk_client.disconnect()
    logger.info("Infrastructure shut down.")


def make_scheduler() -> AsyncIOScheduler:
    """Return a configured (but not yet started) APScheduler instance."""
    return AsyncIOScheduler(timezone="UTC")
