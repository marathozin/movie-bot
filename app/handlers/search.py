import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.main_keyboard import get_main_keyboard
from app.keyboards.movie_keyboard import get_movie_card_keyboard
from app.models.movie import Movie
from app.services import saved as saved_service
from app.services.movie_api import movie_service

from config import settings

from infrastructure.cache.redis_client import redis_client

logger = logging.getLogger(__name__)
router = Router(name="search")


# How many results to show per page
PAGE_SIZE = 1

_RESERVED_TEXTS = {
    "🎲 Случайный фильм",
}


class SearchStates(StatesGroup):
    waiting_query = State()


# Function to display number of films
def display_n_films(n):
    n = abs(n)
    last_two = n % 100
    last_one = n % 10

    if 11 <= last_two <= 14:
        return f"{n} фильмов"
    if last_one == 1:
        return f"{n} фильм"
    elif 2 <= last_one <= 4:
        return f"{n} фильма"
    else:
        return f"{n} фильмов"


# FSM: query typed after pressing the button
@router.message(SearchStates.waiting_query)
async def process_fsm_query(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    await _do_search(message, message.text.strip(), session)


# Plain text fallback (any message not matching a keyboard button)
@router.message(
    F.text,
    StateFilter(None),
    ~F.text.in_(_RESERVED_TEXTS),
    ~F.text.startswith("/"),
)
async def plain_text_search(message: Message, session: AsyncSession) -> None:
    query = message.text.strip()
    if len(query) < 2:
        return
    await _do_search(message, query, session)


# Shared search logic
async def _do_search(message: Message, query: str, session: AsyncSession) -> None:
    if len(query) < 2:
        await message.answer("❗ Запрос слишком короткий. Попробуйте ещё раз.")
        return

    status_msg = await message.answer("🔍 Ищу фильмы...")
    try:
        all_movies, remaining = await movie_service.search_by_keywords(
            user_id=message.from_user.id,
            query=query,
        )
    except PermissionError:
        await status_msg.delete()
        await message.answer(
            f"❗ Вы исчерпали лимит поиска: {settings.SEARCH_DAILY_LIMIT}"
            " запросов в день.\n"
            "Лимит сбросится в полночь по UTC.",
            reply_markup=get_main_keyboard(),
        )
        return

    # Persist session for "Show more" paging
    await movie_service.store_search_session(message.from_user.id, query, all_movies)

    first_page, has_more = await movie_service.get_next_search_page(
        message.from_user.id, PAGE_SIZE
    )

    await redis_client.client.incr(f"user:{message.from_user.id}:request_count")

    await status_msg.delete()

    if not first_page:
        await message.answer(
            f"😔 По запросу *{query}* ничего не найдено.\n"
            "Попробуйте другие ключевые слова.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(),
        )
        return

    await message.answer(
        f"🎬 По запросу *{query}* найдено {display_n_films(len(all_movies))} ",
        parse_mode="Markdown",
    )

    await _send_movie_page(message, first_page, has_more, session)


async def _send_movie_page(
    message: Message, movies: list[Movie], has_more: bool, session: AsyncSession
) -> None:
    """Send a list of movie cards, attaching 'Show more' button to the last one."""
    user_id = message.from_user.id
    saved_ids = await saved_service.get_saved_ids(user_id, session)
    for i, movie in enumerate(movies):
        is_last = i == len(movies) - 1
        try:
            await message.answer(
                movie.format_message(),
                parse_mode="Markdown",
                disable_web_page_preview=False,
                reply_markup=get_movie_card_keyboard(
                    kinopoisk_id=movie.kinopoisk_id,
                    is_saved=movie.kinopoisk_id in saved_ids,
                    show_more_callback=(
                        "more_search" if (is_last and has_more) else None
                    ),
                ),
            )
        except Exception as exc:
            logger.warning("Could not send movie card: %s", exc)


# "Показать ещё"
@router.callback_query(F.data == "more_search")
async def handle_more_search(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer("Загружаю следующие фильмы...")

    next_page, has_more = await movie_service.get_next_search_page(
        callback.from_user.id, PAGE_SIZE
    )

    if not next_page:
        await callback.message.answer("✅ Это все найденные фильмы.")
        return

    await _send_movie_page(callback.message, next_page, has_more, session)
