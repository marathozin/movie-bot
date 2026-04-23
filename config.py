from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ADMIN_API_KEY: str
    
    # Telegram
    BOT_TOKEN: str
    SECRET_TOKEN: str
    WEBHOOK_URL: str | None = None
    WEBHOOK_PATH: str = "/webhook"

    # Кинопоиск
    KINOPOISK_API_KEY: str

    # Redis
    REDIS_URL: str

    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DATABASE_URL: str

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Cache
    CACHE_TTL: int
    MAX_RESULTS_PER_SEARCH: int = 1
    SEARCH_DAILY_LIMIT: int = 10

    model_config = {"env_file": ".env"}


settings = Settings()
