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



def _split_title_body(text: str) -> tuple[str, str]:
    """Отделить первый абзац (заголовок) от остального тела.

    Заголовок = первый непустой блок до первого двойного перевода строки.
    Если заголовок слишком длинный для подписи — вернуть его как есть,
    тело останется пустым (вызывающий код решит, как публиковать).
    """
    stripped = text.strip()
    if not stripped:
        return "", ""
    parts = stripped.split("\n\n", 1)
    title = parts[0].strip()
    rest = parts[1].strip() if len(parts) > 1 else ""
    return title, rest


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
        title, rest = _split_title_body(body)

        if has_image and len(body) <= TG_CAPTION_LIMIT:
            # короткий текст целиком помещается в подпись под фото
            msg = await bot.send_photo(
                chat, FSInputFile(str(image_path)),
                caption=body, parse_mode="HTML",
            )
            first_msg_id = msg.message_id
        elif has_image:
            # фото + заголовок в подписи, тело — отдельными сообщениями
            caption = title if len(title) <= TG_CAPTION_LIMIT else title[:TG_CAPTION_LIMIT]
            msg = await bot.send_photo(
                chat, FSInputFile(str(image_path)),
                caption=caption or None, parse_mode="HTML",
            )
            first_msg_id = msg.message_id
            tail = rest if len(title) <= TG_CAPTION_LIMIT else body
            for part in _split(tail, TG_TEXT_LIMIT):
                if part.strip():
                    await bot.send_message(chat, part, parse_mode="HTML")
        else:
            # без картинки — только текст частями
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
