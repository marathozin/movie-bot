from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_movie_card_keyboard(
    kinopoisk_id: int, is_saved: bool = False, show_more_callback: str | None = None
) -> InlineKeyboardMarkup:
    """
    Keyboard for every movie card.
    """
    more_part = show_more_callback or ""
    save_btn = InlineKeyboardButton(
        text="Удалить" if is_saved else "❤️ Сохранить",
        callback_data=f"save_movie:{kinopoisk_id}:{more_part}",
    )
    if show_more_callback:
        more_btn = InlineKeyboardButton(
            text="🎲 Показать ещё",
            callback_data=show_more_callback,
        )
        return InlineKeyboardMarkup(inline_keyboard=[[save_btn, more_btn]])
    return InlineKeyboardMarkup(inline_keyboard=[[save_btn]])
