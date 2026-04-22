from app.models.movie import Movie


def test_movie_from_api_maps_fields_and_fallbacks():
    raw = {
        "filmId": "1",
        "nameRu": "Фильм",
        "year": "2026",
        "ratingImdb": 9.0,
        "genres": [
            {"id": 1, "genre": "фантастика"},
            {"genre": "драма"}
        ],
        "posterUrlPreview": "https://img/poster.jpg",
    }

    movie = Movie.from_api(raw)

    assert movie.kinopoisk_id == 1
    assert movie.name_ru == "Фильм"
    assert movie.year == 2026
    assert movie.rating == "9.0"
    assert [g.genre for g in movie.genres] == ["фантастика", "драма"]
    assert movie.poster_url == "https://img/poster.jpg"


def test_movie_validators_handle_null_like_values():
    movie = Movie(kinopoisk_id="", year="null", rating="", genres=[])

    assert movie.kinopoisk_id == 0
    assert movie.year == 0
    assert movie.rating is None


def test_format_message_contains_main_fields():
    movie = Movie.from_api(
        {
            "kinopoiskId": 1,
            "nameEn": "MovieName",
            "year": 2026,
            "rating": 9.0,
            "genres": [{"genre": "комедия"}],
            "posterUrl": "https://img/moviename.jpg",
        }
    )

    text = movie.format_message()

    assert "🎬 *MovieName* (2026)" in text
    assert "⭐ 9.0" in text
    assert "🎭 Жанры: комедия" in text
    assert "https://www.kinopoisk.ru/film/1" in text
    assert "[Постер](https://img/moviename.jpg)" in text


def test_format_message_handles_missing_optional_fields():
    movie = Movie(kinopoisk_id=0, genres=[])

    text = movie.format_message()

    assert "Без названия" in text
    assert "Жанры: не указан" in text
    assert "Кинопоиск" not in text
