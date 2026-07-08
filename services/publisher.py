"""Публикация одобренной статьи в канал."""
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile

import config
from db import database as db

logger = logging.getLogger(__name__)

TG_CAPTION_LIMIT = 1024
TG_TEXT_LIMIT = 4096


def _split(text: str, limit: int) -> list[str]:
    """Разбить длинный текст на части по лимиту Telegram."""
    parts, buf = [], ""
    for para in text.split("\n\n"):
        chunk = (buf + "\n\n" + para).strip() if buf else para
        if len(chunk) <= limit:
            buf = chunk
        else:
            if buf:
                parts.append(buf)
            # если сам абзац длиннее лимита — режем жёстко
            while len(para) > limit:
                parts.append(para[:limit])
                para = para[limit:]
            buf = para
    if buf:
        parts.append(buf)
    return parts or [text[:limit]]


async def publish_article(bot: Bot, article_id: int) -> dict:
    """Опубликовать статью в канал. Возвращает {ok, message_id|error}."""
    art = await db.get_article(article_id)
    if not art:
        return {"ok": False, "error": f"Статья #{article_id} не найдена"}

    body = art["body"] or ""
    image_path = art.get("image_path")
    chat = config.CHANNEL_ID
    first_msg_id = None

    try:
        has_image = bool(image_path) and Path(str(image_path)).exists()
        if has_image and len(body) <= TG_CAPTION_LIMIT:
            # фото + весь текст в подписи
            msg = await bot.send_photo(
                chat, FSInputFile(str(image_path)),
                caption=body, parse_mode="HTML",
            )
            first_msg_id = msg.message_id
        elif has_image:
            # фото отдельно, затем текст частями
            msg = await bot.send_photo(chat, FSInputFile(str(image_path)))
            first_msg_id = msg.message_id
            for part in _split(body, TG_TEXT_LIMIT):
                await bot.send_message(chat, part, parse_mode="HTML")
        else:
            # без картинки — только текст
            for i, part in enumerate(_split(body, TG_TEXT_LIMIT)):
                msg = await bot.send_message(chat, part, parse_mode="HTML")
                if i == 0:
                    first_msg_id = msg.message_id
    except Exception as e:
        logger.exception("Ошибка публикации статьи #%s", article_id)
        return {"ok": False, "error": str(e)}

    await db.update_article(
        article_id,
        status="published",
        message_id=first_msg_id,
        published_at=None,  # выставится в SQL ниже
    )
    # published_at через отдельный апдейт (datetime now)
    await _mark_published_time(article_id)
    if art.get("topic_id"):
        await db.set_topic_status(art["topic_id"], "published")

    logger.info("Статья #%s опубликована, msg_id=%s", article_id, first_msg_id)
    return {"ok": True, "message_id": first_msg_id}


async def _mark_published_time(article_id: int):
    import aiosqlite
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute(
            "UPDATE articles SET published_at = datetime('now') WHERE id = ?",
            (article_id,),
        )
        await conn.commit()
