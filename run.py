import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from aiogram.types import Update
from fastapi import FastAPI, Request, Response, Header, Depends, HTTPException

from app.core.bot_setup import bot, dp
from app.core.infrastructure import make_scheduler, shutdown, startup
from app.core.admin_auth import verify_admin_key

from app.services.movie_api import movie_service
from config import settings
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    await startup()

    # Прогрев кеша при старте и каждые 24 часа
    scheduler = make_scheduler()
    scheduler.add_job(movie_service.warm_cache, "interval", hours=24, id="warm_cache")
    scheduler.start()
    asyncio.create_task(movie_service.warm_cache(), name="initial_cache_warm")

    # Регистрация вебхука
    if not settings.WEBHOOK_URL:
        raise RuntimeError(
            "WEBHOOK_URL is required for run.py. "
            "Set it in .env or use bot.py for polling mode."
        )
    
    webhook_url = f"{settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}"
    await bot.set_webhook(
        webhook_url,
        secret_token=settings.SECRET_TOKEN, 
        drop_pending_updates=True
    )
    logger.info("Webhook registered: %s", webhook_url)

    yield

    await bot.delete_webhook()
    scheduler.shutdown(wait=False)
    await bot.session.close()
    await shutdown()
    logger.info("Shutdown complete.")


app = FastAPI(title="Movie Bot", lifespan=lifespan)


@app.post(settings.WEBHOOK_PATH)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None),
) -> Response:
    """Принимает обновления от Telegram и передаёт в aiogram dispatcher."""
    if x_telegram_bot_api_secret_token != settings.SECRET_TOKEN:
        raise HTTPException(status_code=403)
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot=bot, update=update)
    return Response(content="ok")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/admin/refresh-cache", dependencies=[Depends(verify_admin_key)])
async def refresh_cache() -> dict:
    """Manually trigger a full cache warm in the background."""
    asyncio.create_task(movie_service.warm_cache(), name="manual_cache_warm")
    return {"status": "Cache refresh started in background."}


@app.get("/admin/stats", dependencies=[Depends(verify_admin_key)])
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
        "run:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
    )
