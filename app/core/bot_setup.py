from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.handlers import genres, saved, search, start
from app.middleware import DatabaseMiddleware
from config import settings

storage = RedisStorage.from_url(settings.REDIS_URL)

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
)

dp = Dispatcher(storage=storage)
dp.update.middleware(DatabaseMiddleware())

dp.include_router(start.router)
dp.include_router(saved.router)
dp.include_router(genres.router)
dp.include_router(search.router)
