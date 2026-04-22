"""
FastAPI backend entry point.

GET  /health
GET  /admin/stats
POST /admin/refresh-cache
POST {WEBHOOK_PATH}
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request, Response

from app.core.bot_setup import bot, dp
from app.core.infrastructure import shutdown, startup
from app.services.movie_api import movie_service
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# Lifespan
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    await startup()
    logger.info("Backend ready.")
    yield
    await shutdown()
    logger.info("Backend stopped.")


# App
app = FastAPI(title="Movie Bot", lifespan=lifespan)


# Health
@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# Webhook receiver (used when WEBHOOK_URL is configured)
@app.post(settings.WEBHOOK_PATH)
async def telegram_webhook(request: Request) -> Response:
    """
    Receive Telegram updates via webhook and feed them to the dispatcher.
    Active only when WEBHOOK_URL is set in .env.
    In polling mode this endpoint is never called by Telegram.
    """
    from aiogram.types import Update

    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot=bot, update=update)
    return Response(content="ok")


# Admin
@app.post("/admin/refresh-cache")
async def refresh_cache() -> dict:
    """Manually trigger a full cache warm in the background."""
    asyncio.create_task(movie_service.warm_cache(), name="manual_cache_warm")
    return {"status": "Cache refresh started in background."}


@app.get("/admin/stats")
async def stats() -> dict:
    """Return live Redis and Postgres statistics."""
    from sqlalchemy import func, select
    from infrastructure.cache.redis_client import redis_client
    from infrastructure.db.database import async_session_factory
    from infrastructure.db.models import CachedMovie, User

    user_counter_keys = await redis_client.keys("user:*:request_count")

    # Create dict: user_id -> count
    per_user_requests = {}
    total_requests = 0
    if user_counter_keys:
        user_ids = [
            key.split(":")[1] for key in user_counter_keys
        ]  # "user:123:request_count" -> "123"
        counts = await redis_client.client.mget(*user_counter_keys)
        for user_id, count in zip(user_ids, counts):
            if count:
                c = int(count)
                per_user_requests[f"id{user_id}"] = c
                total_requests += c

    movie_keys = await redis_client.keys("movie:*")
    genre_index_keys = await redis_client.keys("index:genre:*")

    async with async_session_factory() as session:
        total_users = (
            await session.execute(select(func.count()).select_from(User))
        ).scalar()
        total_cached_movies = (
            await session.execute(select(func.count()).select_from(CachedMovie))
        ).scalar()

    return {
        "redis": {
            "movies_cached": len(movie_keys),
            "genre_indexes": len(genre_index_keys),
            "total_requests": total_requests,
            "per_user_requests": per_user_requests,
        },
        "postgres": {
            "users": total_users,
            "cached_movies": total_cached_movies,
        },
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level="info",
    )
