from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Случайный фильм")],
            [KeyboardButton(text="❤️ Сохранённые фильмы")],
        ],
        resize_keyboard=True,
    )
