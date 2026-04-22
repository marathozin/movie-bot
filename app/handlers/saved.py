import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.keyboards.movie_keyboard import get_movie_card_keyboard
from infrastructure.db.models import SavedMovie
from app.models.movie import Movie
from app.services.movie_api import movie_key
from infrastructure.cache.redis_client import redis_client

logger = logging.getLogger(__name__)
router = Router(name="saved")


# Сохранение / отмена через inline-кнопку
@router.callback_query(F.data.startswith("save_movie:"))
async def toggle_save(callback: CallbackQuery, session: AsyncSession) -> None:
    _, kinopoisk_id_str, more_part = callback.data.split(":", 2)
    kinopoisk_id = int(kinopoisk_id_str)
    show_more_callback = more_part or None
    user_id = callback.from_user.id

    result = await session.execute(
        select(SavedMovie).where(
            SavedMovie.user_id == user_id,
            SavedMovie.kinopoisk_id == kinopoisk_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        await session.delete(existing)
        await session.commit()
        await callback.answer("Удалено из сохранённых.")
        is_saved = False
    else:
        session.add(SavedMovie(user_id=user_id, kinopoisk_id=kinopoisk_id))
        await session.commit()
        await callback.answer("Сохранено! ❤️")
        is_saved = True

    # Обновить кнопку под фильмом
    await callback.message.edit_reply_markup(
        reply_markup=get_movie_card_keyboard(
            kinopoisk_id, is_saved=is_saved, show_more_callback=show_more_callback
        )
    )


# Просмотр списка сохранённых
@router.message(F.text == "❤️ Сохранённые фильмы")
async def show_saved(message: Message, session: AsyncSession) -> None:
    result = await session.execute(
        select(SavedMovie)
        .where(SavedMovie.user_id == message.from_user.id)
        .order_by(desc(SavedMovie.saved_at))
        .limit(20)
    )
    records = result.scalars().all()

    if not records:
        await message.answer("У вас нет сохранённых фильмов.")
        return

    for rec in records:
        data = await redis_client.get_json(movie_key(rec.kinopoisk_id))
        if data:
            movie = Movie(**data)
            await message.answer(
                movie.format_message(),
                parse_mode="Markdown",
                reply_markup=get_movie_card_keyboard(rec.kinopoisk_id, is_saved=True),
            )
