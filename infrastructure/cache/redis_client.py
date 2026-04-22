import json
import logging
from typing import Any

import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client wrapper."""

    def __init__(self) -> None:
        self._client: aioredis.Redis | None

    async def connect(self) -> None:
        self._client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            encoding="utf-8",
        )
        await self._client.ping()
        logger.info("Redis connected.")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            logger.info("Redis disconnected.")

    @property
    def client(self) -> aioredis.Redis:
        if not self._client:
            raise RuntimeError("Redis client is not connected. Call connect() first.")
        return self._client

    async def set_json(
        self, key: str, data: Any, ttl: int = settings.CACHE_TTL
    ) -> None:
        await self.client.setex(key, ttl, json.dumps(data, ensure_ascii=False))

    async def get_json(self, key: str) -> Any | None:
        raw = await self.client.get(key)
        return json.loads(raw) if raw else None

    async def sadd_with_ttl(
        self, key: str, *members: str, ttl: int = settings.CACHE_TTL
    ) -> None:
        pipe = self.client.pipeline()
        pipe.sadd(key, *members)
        pipe.expire(key, ttl)
        await pipe.execute()

    async def smembers(self, key: str) -> set[str]:
        return await self.client.smembers(key)

    async def srandmember(self, key: str) -> str | None:
        return await self.client.srandmember(key)

    async def exists(self, *keys: str) -> int:
        return await self.client.exists(*keys)

    async def delete(self, *keys: str) -> int:
        return await self.client.delete(*keys)

    async def keys(self, pattern: str) -> list[str]:
        return await self.client.keys(pattern)


redis_client = RedisClient()
