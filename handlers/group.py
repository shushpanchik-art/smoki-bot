from aiogram import Router, F
from aiogram.types import Message

import config
from db import database

router = Router(name="group")


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def collect_group_message(message: Message):
    # Реагируем только на привязанную группу-обсуждение (если задана)
    if config.DISCUSSION_GROUP_ID and message.chat.id != config.DISCUSSION_GROUP_ID:
        return
    # Пропускаем сервисные пересылки самого канала (авто-пост в обсуждение)
    if message.from_user is None or message.from_user.is_bot:
        return
    text = message.text or message.caption or ""
    if not text.strip():
        return
    await database.add_comment(
        chat_id=message.chat.id,
        message_id=message.message_id,
        user_id=message.from_user.id,
        username=message.from_user.username or message.from_user.full_name,
        text=text,
    )
