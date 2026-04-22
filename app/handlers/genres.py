import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.genre_keyboard import GENRE_DISPLAY, get_genre_keyboard
from app.keyboards.movie_keyboard import get_movie_card_keyboard
from app.services.movie_api import movie_service
from app.services import saved as saved_service

from infrastructure.cache.redis_client import redis_client

logger = logging.getLogger(__name__)
router = Router(name="genres")


# "Random movie" button or /random command
@router.message(F.text == "🎲 Случайный фильм")
@router.message(Command("random"))
async def btn_random(message: Message) -> None:
    await message.answer("🎭 Выберите жанр:", reply_markup=get_genre_keyboard())


# Genre selected
@router.callback_query(F.data.startswith("genre:"))
async def handle_genre_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    genre_name = callback.data.split(":", 1)[1]
    genre_label = GENRE_DISPLAY.get(genre_name, genre_name)

    # Remove the genre keyboard immediately (clean UX)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()

    status = await callback.message.answer(
        f"🎲 Ищу случайный фильм в жанре *{genre_label}*...", parse_mode="Markdown"
    )

    movie = await movie_service.get_random_by_genre(
        genre_name, user_id=callback.from_user.id
    )

    await redis_client.client.incr(f"user:{callback.from_user.id}:request_count")

    await status.delete()

    if not movie:
        await callback.message.answer(
            f"😔 Фильмы жанра *{genre_label}* ещё не загружены.\n"
            "Кеш обновляется раз в 24 ч — попробуйте чуть позже"
            "или выберите другой жанр.",
            parse_mode="Markdown",
        )
        return

    is_saved = await saved_service.is_movie_saved(
        callback.from_user.id, movie.kinopoisk_id, session
    )

    await callback.message.answer(
        f"🎲 Случайный фильм - *{genre_label}*:\n\n{movie.format_message()}",
        parse_mode="Markdown",
        disable_web_page_preview=False,
        reply_markup=get_movie_card_keyboard(
            kinopoisk_id=movie.kinopoisk_id,
            is_saved=is_saved,
            show_more_callback=f"more_random:{genre_name}",
        ),
    )


# "Показать ещё"
@router.callback_query(F.data.startswith("more_random:"))
async def handle_more_random(callback: CallbackQuery, session: AsyncSession) -> None:
    genre_name = callback.data.split(":", 1)[1]
    genre_label = GENRE_DISPLAY.get(genre_name, genre_name)

    await callback.answer("Ищу другой фильм...")

    movie = await movie_service.get_random_by_genre(
        genre_name, user_id=callback.from_user.id
    )

    await redis_client.client.incr(f"user:{callback.from_user.id}:request_count")

    if not movie:
        await callback.message.answer(
            f"😔 Не удалось найти ещё один фильм в жанре *{genre_label}*.",
            parse_mode="Markdown",
        )
        return

    is_saved = await saved_service.is_movie_saved(
        callback.from_user.id, movie.kinopoisk_id, session
    )

    await callback.message.answer(
        f"🎲 Ещё один фильм - *{genre_label}*:\n\n{movie.format_message()}",
        parse_mode="Markdown",
        disable_web_page_preview=False,
        reply_markup=get_movie_card_keyboard(
            kinopoisk_id=movie.kinopoisk_id,
            is_saved=is_saved,
            show_more_callback=f"more_random:{genre_name}",
        ),
    )
