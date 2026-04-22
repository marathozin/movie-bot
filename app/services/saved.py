from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from infrastructure.db.models import SavedMovie


async def is_movie_saved(
    user_id: int, kinopoisk_id: int, session: AsyncSession
) -> bool:
    result = await session.execute(
        select(SavedMovie).where(
            SavedMovie.user_id == user_id,
            SavedMovie.kinopoisk_id == kinopoisk_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def get_saved_ids(user_id: int, session: AsyncSession) -> set[int]:
    """Fetch all saved kinopoisk_ids for a user in one query."""
    result = await session.execute(
        select(SavedMovie.kinopoisk_id).where(SavedMovie.user_id == user_id)
    )
    return set(result.scalars().all())
