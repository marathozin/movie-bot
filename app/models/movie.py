from pydantic import BaseModel, field_validator


class Genre(BaseModel):
    id: int | None = None
    genre: str = ""


class Movie(BaseModel):
    kinopoisk_id: int
    name_ru: str | None = None
    name_en: str | None = None
    year: int | None = None
    rating: str | None = None
    genres: list[Genre] = []
    description: str | None = None
    poster_url: str | None = None

    @field_validator("rating", mode="before")
    @classmethod
    def coerce_rating(cls, v: object) -> str | None:
        if v is None or v == "null" or v == "":
            return None
        return str(v)

    @field_validator("kinopoisk_id", "year", mode="before")
    @classmethod
    def coerce_int(cls, v: object) -> int | None:
        if v is None or v == "null" or v == "":
            return 0
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    # Factory
    @classmethod
    def from_api(cls, data: dict) -> "Movie":
        """Build a Movie from a raw Kinopoisk API response item."""
        genres = [
            Genre(id=g.get("id"), genre=g.get("genre", ""))
            for g in data.get("genres", [])
            if isinstance(g, dict)
        ]

        rating = (
            data.get("ratingKinopoisk") or data.get("ratingImdb") or data.get("rating")
        )
        kinopoisk_id = data.get("kinopoiskId") or data.get("filmId") or 0

        return cls(
            kinopoisk_id=kinopoisk_id,
            name_ru=data.get("nameRu") or None,
            name_en=data.get("nameEn") or None,
            year=data.get("year") or None,
            rating=rating,
            genres=genres,
            description=data.get("description") or None,
            poster_url=data.get("posterUrl") or data.get("posterUrlPreview") or None,
        )

    # Presentation
    def format_message(self) -> str:
        name = self.name_ru or self.name_en or "Без названия"
        year_str = f" ({self.year})" if self.year else ""
        rating_str = f"⭐ {self.rating}" if self.rating else ""
        genres_str = ", ".join(g.genre for g in self.genres if g.genre) or "не указан"

        lines = [
            f"🎬 *{name}*{year_str}",
            rating_str,
            f"🎭 Жанры: {genres_str}",
        ]
        if self.kinopoisk_id:
            lines.append(
                "\n*Ссылка на Кинопоиск: "
                f"https://www.kinopoisk.ru/film/{self.kinopoisk_id}*"
            )
        if self.poster_url:
            lines.append(f"\n[Постер]({self.poster_url})")

        return "\n".join(line for line in lines if line)
