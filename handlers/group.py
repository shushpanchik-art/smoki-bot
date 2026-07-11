from aiogram import Router, F
from aiogram.types import Message

import config
from db import database

router = Router(name="group")

# Служебный аккаунт Telegram, от имени которого приходят автопересылки
# постов канала в привязанную группу-обсуждение.
TELEGRAM_SERVICE_USER_ID = 777000


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def collect_group_message(message: Message) -> None:
    # Реагируем только на привязанную группу-обсуждение (если задана)
    if config.DISCUSSION_GROUP_ID and message.chat.id != config.DISCUSSION_GROUP_ID:
        return
    # Автопересылка поста самого канала в обсуждение — это не комментарий
    if message.is_automatic_forward:
        return
    # Сообщение от имени канала/чата (sender_chat), а не от пользователя
    if message.sender_chat is not None:
        return
    # Нет автора, бот или служебный аккаунт Telegram — пропускаем
    if message.from_user is None or message.from_user.is_bot:
        return
    if message.from_user.id == TELEGRAM_SERVICE_USER_ID:
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
