from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import config

router = Router(name="admin")


def _is_admin(message: Message) -> bool:
    return config.ADMIN_CHAT_ID and message.from_user.id == config.ADMIN_CHAT_ID


@router.message(Command("id"))
async def cmd_id(message: Message):
    """Служебная: показывает chat_id текущего чата и id пользователя."""
    await message.answer(
        f"chat_id этого чата: <code>{message.chat.id}</code>\n"
        f"тип чата: {message.chat.type}\n"
        f"твой user_id: <code>{message.from_user.id}</code>"
    )


@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.chat.type != "private":
        return
    if not _is_admin(message):
        await message.answer(
            "Это служебный бот автоведения канала SMOKI.\n"
            f"Твой user_id: <code>{message.from_user.id}</code>\n"
            "Если ты администратор — впиши этот id в ADMIN_CHAT_ID (.env)."
        )
        return
    await message.answer(
        "👋 SMOKI content bot готов.\n\n"
        "Команды:\n"
        "/generate — сгенерировать черновик поста (появится позже)\n"
        "/id — показать id чата"
    )
