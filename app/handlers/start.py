import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.main_keyboard import get_main_keyboard
from infrastructure.db.models import User
import os

logger = logging.getLogger(__name__)
router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    tg = message.from_user

    result = await session.execute(select(User).where(User.telegram_id == tg.id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            telegram_id=tg.id,
            username=tg.username,
            first_name=tg.first_name,
        )
        session.add(user)
        await session.commit()
        greeting = f"👋 Привет, {tg.first_name}!"
    else:
        greeting = f"👋 С возвращением, {tg.first_name}!"

    current_dir = os.path.dirname(__file__)
    file_path = os.path.join(current_dir, "..", "..", "messages", "start_message.txt")
    with open(file_path, "r", encoding="utf-8") as f:
        message_text = f.read()

    await message.answer(
        f"{greeting}\n\n",
        message_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    current_dir = os.path.dirname(__file__)
    file_path = os.path.join(current_dir, "..", "..", "messages", "help.txt")
    with open(file_path, "r", encoding="utf-8") as f:
        help_text = f.read()
    await message.answer(
        help_text,
        parse_mode="Markdown",
    )
