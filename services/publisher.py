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
        first_msg_id = await send_photo_with_text(
            bot, chat, image_path, body,
        )
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


def _caption_split(text: str, limit: int = TG_CAPTION_LIMIT) -> tuple[str, str]:
    """Отделить кусок для caption (<=limit, по границе абзаца) и остаток.

    Caption = как можно больше текста, но не длиннее limit и по возможности
    заканчивается на границе абзаца (\\n\\n). Если первый абзац сам длиннее
    limit — жёсткая обрезка по limit. Возвращает (caption, tail).
    """
    text = (text or "").strip()
    if not text:
        return "", ""
    if len(text) <= limit:
        return text, ""
    paras = text.split("\n\n")
    cap = ""
    for i, para in enumerate(paras):
        cand = (cap + "\n\n" + para).strip() if cap else para
        if len(cand) <= limit:
            cap = cand
        else:
            break
    if cap:
        tail = text[len(cap):].strip()
        return cap, tail
    # первый абзац длиннее лимита — жёсткая обрезка
    return text[:limit], text[limit:].strip()


async def send_photo_with_text(
    bot: Bot,
    chat_id: int | str,
    image_path: str | None,
    text: str,
    header: str = "",
    reply_markup=None,
):
    """Отправить фото с максимумом текста в подписи, остаток — сообщениями.

    header (напр. "Черновик #12") идёт в начало подписи/первого сообщения.
    Кнопки reply_markup вешаются на ПОСЛЕДНЕЕ сообщение.
    Возвращает message_id первого сообщения (или None).
    """
    has_img = bool(image_path) and Path(str(image_path)).exists()
    full = (header + text) if header else text
    first_id = None

    if has_img:
        cap, tail = _caption_split(full, TG_CAPTION_LIMIT)
        try:
            msg = await bot.send_photo(
                chat_id, FSInputFile(str(image_path)),
                caption=cap or None, parse_mode="HTML",
                reply_markup=reply_markup if not tail else None,
            )
            first_id = msg.message_id
        except Exception:
            logger.exception("send_photo_with_text: фото не отправилось")
            has_img = False
            tail = full  # весь текст пойдёт сообщениями
        if has_img and tail:
            parts = _split(tail, TG_TEXT_LIMIT)
            for i, part in enumerate(parts):
                if not part.strip():
                    continue
                last = i == len(parts) - 1
                await bot.send_message(
                    chat_id, part, parse_mode="HTML",
                    reply_markup=reply_markup if last else None,
                )
        return first_id

    # без фото — только текст частями
    parts = _split(full, TG_TEXT_LIMIT)
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        msg = await bot.send_message(
            chat_id, part, parse_mode="HTML",
            reply_markup=reply_markup if last else None,
        )
        if i == 0:
            first_id = msg.message_id
    return first_id
