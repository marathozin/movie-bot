import asyncio
import json
import logging
import re

from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert

from config import settings
from infrastructure.api.kinopoisk import kinopoisk_client
from infrastructure.cache.redis_client import redis_client
from infrastructure.db.database import async_session_factory
from infrastructure.db.models import CachedMovie
from app.models.movie import Movie

logger = logging.getLogger(__name__)


def _slug(text: str) -> str:
    """Normalise text to a safe Redis key segment."""
    return re.sub(r"[^a-z0-9а-яё]", "_", text.lower())[:50]


def movie_key(kinopoisk_id: int) -> str:
    return f"movie:{kinopoisk_id}"


def genre_index_key(genre_name: str) -> str:
    return f"index:genre:{genre_name}"


def search_results_key(user_id: int) -> str:
    return f"search_results:{user_id}"


def last_random_key(user_id: int, genre_name: str) -> str:
    return f"last_random:{user_id}:{genre_name}"


def search_quota_key(user_id: int) -> str:
    return f"search_quota:{user_id}"

CACHE_WARMED_KEY = "cache:warmed"

def _seconds_until_midnight_utc() -> int:
    """Seconds remaining until 00:00 UTC - used as TTL for the daily quota key."""
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    from datetime import timedelta

    midnight += timedelta(days=1)
    return int((midnight - now).total_seconds())


class MovieService:
    async def warm_cache(self) -> None:
        """
        Fetch pages of TOP_POPULAR_MOVIES in parallel (semaphore=10)
        and build all Redis indexes. Runs once at startup and every 24 h.
        """
        if await redis_client.exists(CACHE_WARMED_KEY):
            logger.info('Cache already warmed, skipping.')
            return
        
        # Fetch page 1 to discover totalPages
        try:
            first = await kinopoisk_client.get_collection(page=1)
        except Exception as exc:
            logger.error(f"Could not fetch collection page 1: {exc}")
            return

        total_pages = first.get("totalPages", 1)

        logger.info(
            f"Cache warming started (TOP_POPULAR_MOVIES, {total_pages} pages).",
        )
        semaphore = asyncio.Semaphore(10)

        async def _fetch_page(page: int) -> tuple[int, dict | None]:
            async with semaphore:
                try:
                    data = await kinopoisk_client.get_collection(page=page)
                    return page, data
                except Exception as exc:
                    logger.warning(f"Collection page {page} failed: {exc}")
                    return page, None

        # Fetch remaining pages in parallel (page 1 already fetched)
        tasks = [_fetch_page(p) for p in range(2, total_pages + 1)]
        results = await asyncio.gather(*tasks)

        # Combine page 1 with the rest
        all_responses = [(1, first)] + list(results)

        all_movies: list[Movie] = []
        for _page, data in all_responses:
            if not data:
                continue
            items = data.get("items", [])
            for item in items:
                try:
                    all_movies.append(Movie.from_api(item))
                except Exception as exc:
                    logger.debug(f"Skipping incorrect movie item: {exc}")

        if not all_movies:
            logger.error("Cache warming produced 0 movies. Check API key or quota.")
            return

        # Create list of unique movies by id
        seen: set[int] = set()
        unique_movies: list[Movie] = []
        for m in all_movies:
            if m.kinopoisk_id not in seen:
                seen.add(m.kinopoisk_id)
                unique_movies.append(m)

        logger.info(f"Fetched {len(unique_movies)} unique movies. Building indexes...")
        await self._index_all(unique_movies)
        logger.info("Cache warming complete.")

    async def _index_all(self, movies: list[Movie]) -> None:
        """Store movies in Redis and Postgres, build genre indexes."""
        genre_buckets: dict[str, list[str]] = {}
        db_rows: list[dict] = []

        for m in movies:
            mid = str(m.kinopoisk_id)

            await redis_client.set_json(movie_key(m.kinopoisk_id), m.model_dump())

            # Genre index buckets
            for g in m.genres:
                if g.genre:
                    genre_buckets.setdefault(_slug(g.genre), []).append(mid)

            # Postgres row
            db_rows.append(
                {
                    "kinopoisk_id": m.kinopoisk_id,
                    "name_ru": m.name_ru,
                    "name_en": m.name_en,
                    "year": m.year,
                    "rating": m.rating,
                    "genres_json": json.dumps(
                        [g.model_dump() for g in m.genres], ensure_ascii=False
                    ),
                    "description": m.description,
                    "poster_url": m.poster_url,
                }
            )

        for name, ids in genre_buckets.items():
            await redis_client.sadd_with_ttl(genre_index_key(name), *ids)

        # Postgres upsert batch
        batch_size = 500
        for i in range(0, len(db_rows), batch_size):
            batch = db_rows[i: i + batch_size]
            async with async_session_factory() as session:
                stmt = pg_insert(CachedMovie).values(batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["kinopoisk_id"],
                    set_={
                        "name_ru": stmt.excluded.name_ru,
                        "name_en": stmt.excluded.name_en,
                        "year": stmt.excluded.year,
                        "rating": stmt.excluded.rating,
                        "genres_json": stmt.excluded.genres_json,
                        "description": stmt.excluded.description,
                        "poster_url": stmt.excluded.poster_url,
                    },
                )
                await session.execute(stmt)
                await session.commit()

        logger.info(
            f"Indexed {len(genre_buckets)} genre buckets, {len(db_rows)} Postgres rows."
        )

    # Keyword search
    async def check_search_quota(self, user_id: int) -> tuple[bool, int]:
        """
        Check and increment the user's daily API search counter.
        Returns (allowed, remaining_requests).
        Counter resets at midnight UTC.
        """
        key = search_quota_key(user_id)
        count = await redis_client.client.incr(key)

        if count == 1:
            await redis_client.client.expireat(
                key,
                _seconds_until_midnight_utc()
                + int(datetime.now(timezone.utc).timestamp()),
            )

        remaining = max(0, settings.SEARCH_DAILY_LIMIT - count)
        allowed = count <= settings.SEARCH_DAILY_LIMIT
        return allowed, remaining

    async def search_by_keywords(
        self, user_id: int, query: str
    ) -> tuple[list[Movie], int]:
        """
        Search via Kinopoisk API.
        Rate-limited to SEARCH_DAILY_LIMIT requests per user per day.
        Returns (movies, remaining_quota).
        Raises PermissionError when quota is exceeded.
        """
        query = query.strip()[:100]
        if not query:
            return [], 0

        allowed, remaining = await self.check_search_quota(user_id)
        if not allowed:
            raise PermissionError("daily_limit_exceeded")

        try:
            data = await kinopoisk_client.search_by_keyword(query, page=1)
        except Exception as exc:
            logger.error(f"API keyword search failed: {exc}")
            return [], remaining

        items = data.get("films", [])
        movies = [Movie.from_api(item) for item in items]

        for m in movies:
            await redis_client.set_json(movie_key(m.kinopoisk_id), m.model_dump())

        logger.info(
            f"Keyword search '{query}' by user {user_id}:"
            f"{len(movies)} results, {remaining} quota remaining."
        )
        return movies, remaining

    # Paginated search results per user
    async def store_search_session(
        self, user_id: int, query: str, movies: list[Movie]
    ) -> None:
        """Persist search result IDs for a user so 'Show more' can page through them."""
        payload = {
            "query": query,
            "ids": [m.kinopoisk_id for m in movies],
            "offset": 0,
        }
        await redis_client.set_json(search_results_key(user_id), payload, ttl=3600)

    async def get_next_search_page(
        self, user_id: int, page_size: int
    ) -> tuple[list[Movie], bool]:
        """
        Returns (movies_for_this_page, has_more).
        Advances the stored offset by page_size.
        """
        payload = await redis_client.get_json(search_results_key(user_id))
        if not payload:
            return [], False

        ids: list[int] = payload["ids"]
        offset: int = payload["offset"]

        page_ids = ids[offset: offset + page_size]
        if not page_ids:
            return [], False

        movies: list[Movie] = []
        for mid in page_ids:
            data = await redis_client.get_json(movie_key(mid))
            if data:
                movies.append(Movie(**data))

        new_offset = offset + page_size
        payload["offset"] = new_offset
        await redis_client.set_json(search_results_key(user_id), payload, ttl=3600)

        has_more = new_offset < len(ids)
        return movies, has_more

    # Random by genre
    async def get_random_by_genre(self, genre_name: str, user_id: int) -> Movie | None:
        """
        Pick a random movie from index:genre:{name}.
        Tries up to 5 times to avoid the last movie shown to this user.
        """
        idx_key = genre_index_key(genre_name)

        if not await redis_client.exists(idx_key):
            logger.info(
                f"Genre index '{genre_name}' missing — cache may not be warm yet."
            )
            return None

        last_key = last_random_key(user_id, genre_name)
        last_id = await redis_client.get_json(last_key)

        chosen_id: str | None = None
        candidate: str | None = None
        for _ in range(5):
            candidate = await redis_client.srandmember(idx_key)
            if candidate and candidate != str(last_id):
                chosen_id = candidate
                break
        else:
            # All 5 attempts returned the same ID - just use it
            chosen_id = candidate

        if not chosen_id:
            return None

        # Remember last shown
        await redis_client.set_json(last_key, int(chosen_id), ttl=3600)

        data = await redis_client.get_json(movie_key(int(chosen_id)))
        return Movie(**data) if data else None


movie_service = MovieService()
