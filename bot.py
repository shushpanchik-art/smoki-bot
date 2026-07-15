import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    MenuButtonCommands,
)

import config
from db import database
from handlers import ROUTERS
import scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("smoki")

ADMIN_COMMANDS = [
    BotCommand(command="start", description="Панель управления"),
    BotCommand(command="generate", description="Сгенерировать пост"),
    BotCommand(command="generate_morning", description="Утренний пост"),
    BotCommand(command="generate_evening", description="Вечерний лонг-рид"),
    BotCommand(command="setlen", description="Задать длину поста"),
    BotCommand(command="id", description="Показать мой chat id"),
]


async def setup_bot_menu(bot: Bot) -> None:
    """Меню команд: полный набор для админа, пусто для остальных."""
    await bot.set_my_commands([], scope=BotCommandScopeDefault())
    if config.ADMIN_CHAT_ID:
        await bot.set_my_commands(
            ADMIN_COMMANDS,
            scope=BotCommandScopeChat(chat_id=config.ADMIN_CHAT_ID),
        )
        await bot.set_chat_menu_button(
            chat_id=config.ADMIN_CHAT_ID,
            menu_button=MenuButtonCommands(),
        )
    logger.info("Меню команд бота настроено")


async def main():
    if not config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN пуст. Заполни .env")

    await database.init_db()
    logger.info("БД инициализирована: %s", config.DB_PATH)

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    for r in ROUTERS:
        dp.include_router(r)

    me = await bot.get_me()
    logger.info("Бот запущен: @%s (id=%s)", me.username, me.id)

    await setup_bot_menu(bot)
    scheduler.start(bot)
    from services import schedule_control
    await schedule_control.apply_persisted_pauses()
    logger.info("Планировщик активирован")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Остановка бота")
