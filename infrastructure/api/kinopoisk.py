import logging
from typing import Any, Dict

import httpx

from config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://kinopoiskapiunofficial.tech/api"


class KinopoiskClient:
    """Async HTTP client for the Kinopoisk Unofficial API."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                "X-API-KEY": settings.KINOPOISK_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        logger.info("Kinopoisk HTTP client initialized.")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            logger.info("Kinopoisk HTTP client closed.")

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError(
                "KinopoiskClient is not connected. Call connect() first."
            )
        return self._client

    async def get_collection(
        self,
        *,
        collection_type: str = "TOP_POPULAR_MOVIES",
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        GET /v2.2/films/collections?type=TOP_POPULAR_MOVIES&page={n}
        """
        response = await self.client.get(
            "/v2.2/films/collections",
            params={"type": collection_type, "page": page},
        )
        response.raise_for_status()
        return response.json()

    async def search_by_keyword(self, keyword: str, page: int = 1) -> Dict[str, Any]:
        """
        GET /v2.1/films/search-by-keyword?keyword={k}&page={n}
        """
        response = await self.client.get(
            "/v2.1/films/search-by-keyword",
            params={"keyword": keyword, "page": page},
        )
        response.raise_for_status()
        return response.json()

    async def get_film_by_id(self, film_id: int) -> Dict[str, Any]:
        """GET /v2.2/films/{id}"""
        response = await self.client.get(f"/v2.2/films/{film_id}")
        response.raise_for_status()
        return response.json()


kinopoisk_client = KinopoiskClient()
