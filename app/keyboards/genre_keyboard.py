from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Genre names from kinopoiskapiunofficial.tech /v2.2/films/filters
GENRES: list[dict] = [
    {"name": "триллер", "emoji": "😱"},
    {"name": "драма", "emoji": "🎭"},
    {"name": "криминал", "emoji": "🔫"},
    {"name": "мелодрама", "emoji": "💕"},
    {"name": "детектив", "emoji": "🕵️"},
    {"name": "фантастика", "emoji": "🚀"},
    {"name": "приключения", "emoji": "🌍"},
    {"name": "биография", "emoji": "📖"},
    {"name": "боевик", "emoji": "🥊"},
    {"name": "фэнтези", "emoji": "🧙"},
    {"name": "комедия", "emoji": "😂"},
    {"name": "военный", "emoji": "⚔️"},
    {"name": "история", "emoji": "🏛️"},
    {"name": "ужасы", "emoji": "👻"},
    {"name": "мультфильм", "emoji": "🎨"},
    {"name": "семейный", "emoji": "👨‍👩‍👧‍👦"},
    {"name": "документальный", "emoji": "📹"},
    {"name": "аниме", "emoji": "💢"},
]

# GENRE_DISPLAY used in handlers to build reply emojis
GENRE_DISPLAY: dict[str, str] = {
    g["name"]: f'{g["emoji"]} {g['name'].capitalize()}' for g in GENRES
}


def get_genre_keyboard() -> InlineKeyboardMarkup:
    """2-column inline keyboard with all genres."""
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for genre in sorted(GENRES, key=lambda x: x["name"]):
        # callback_data: genre:{name}
        row.append(
            InlineKeyboardButton(
                text=GENRE_DISPLAY[genre["name"]],
                callback_data=f"genre:{genre['name']}",
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)
