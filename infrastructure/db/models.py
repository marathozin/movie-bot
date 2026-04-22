from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    String,
    Text,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.database import Base


class User(Base):
    """Telegram users."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_activity: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class CachedMovie(Base):
    """Persistent Postgres mirror of movies fetched from the API."""

    __tablename__ = "cached_movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kinopoisk_id: Mapped[int] = mapped_column(
        Integer, unique=True, index=True, nullable=False
    )
    name_ru: Mapped[str | None] = mapped_column(String(500), nullable=True)
    name_en: Mapped[str | None] = mapped_column(String(500), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    genres_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cached_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SavedMovie(Base):
    __tablename__ = "saved_movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    kinopoisk_id: Mapped[int] = mapped_column(Integer, nullable=False)
    saved_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "kinopoisk_id", name="uq_user_movie"),
    )
