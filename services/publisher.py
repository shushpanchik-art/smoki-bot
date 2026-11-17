"""Публикация одобренной статьи в канал."""
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramMigrateToChat,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramUnauthorizedError,
)
from aiogram.types import FSInputFile

import config
from db import article_publication
from db import database as db
from services import webhooks

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


# These errors carry a rejection from Telegram. Network and server errors
# leave the delivery uncertain, including a lost response after acceptance.
_REJECTED = (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramMigrateToChat,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramUnauthorizedError,
)


async def publish_article(bot: Bot, article_id: int) -> dict:
    """Publish an article through the same durable path for all callers."""
    try:
        return await _publish_article(bot, article_id)
    except Exception:
        logger.exception("Ошибка сохранения прогресса публикации #%s", article_id)
        return {"ok": False, "error": "Не удалось завершить публикацию. Проверь журнал и БД."}


async def _publish_article(bot: Bot, article_id: int) -> dict:
    art = await db.get_article(article_id)
    if not art:
        return {"ok": False, "error": f"Статья #{article_id} не найдена"}
    if art["status"] == "published":
        if (art["message_id"] or 0) > 0:
            return {"ok": True, "message_id": art["message_id"]}
        return {"ok": False, "error": "У старой публикации нет message_id. Требуется сверка."}
    if art["status"] not in ("pending", "approved"):
        return {"ok": False, "error": "Статья снята с публикации."}

    chat_id = str(config.CHANNEL_ID)
    parts = await article_publication.prepare(
        article_id, chat_id, article_parts(art["body"] or "", art["image_path"]),
    )
    for part in parts:
        position = part["position"]
        if part["chat_id"] != chat_id:
            return {"ok": False, "error": "Канал публикации изменился. Требуется сверка."}
        if part["state"] == "confirmed":
            continue
        if part["state"] == "uncertain":
            return _uncertain(position)

        image = part["image_path"]
        if image and not Path(image).is_file():
            return {"ok": False, "error": f"Файл фото отсутствует. Часть {position} ожидает отправки."}
        if not await article_publication.claim(article_id, position):
            return _uncertain(position)

        try:
            if image:
                msg = await bot.send_photo(
                    chat_id, FSInputFile(image), caption=part["text"] or None, parse_mode="HTML",
                )
            else:
                msg = await bot.send_message(chat_id, part["text"], parse_mode="HTML")
        except _REJECTED as exc:
            logger.warning("Telegram отклонил статью #%s, часть %s: %s", article_id, position, exc)
            await article_publication.resolve(article_id, position, None)
            return {"ok": False, "error": f"Telegram отклонил часть {position} ({type(exc).__name__})."}
        except Exception:
            logger.exception("Неизвестный исход публикации #%s, часть %s", article_id, position)
            return _uncertain(position)

        if msg.message_id <= 0:
            logger.warning("Telegram не вернул положительный message_id для #%s, часть %s", article_id, position)
            return _uncertain(position)
        # A failure writing this acknowledgement leaves the committed claim
        # in place. Releasing it here could resend a message Telegram accepted.
        try:
            await article_publication.resolve(article_id, position, msg.message_id)
        except Exception:
            logger.exception(
                "Telegram подтвердил статью #%s, часть %s, message_id=%s, ошибка записи в БД",
                article_id, position, msg.message_id,
            )
            return _uncertain(position)

    first_msg_id, changed = await article_publication.finish(article_id)
    if first_msg_id is None:
        return {"ok": False, "error": "Публикация не завершена. Требуется сверка статьи."}
    if changed:
        logger.info("Статья #%s опубликована, msg_id=%s", article_id, first_msg_id)
        message_url = f"https://t.me/{chat_id[1:]}/{first_msg_id}" if chat_id.startswith("@") else None
        await webhooks.send_webhook("article_published", {
            "article_id": article_id,
            "title": art.get("topic") or "Без темы",
            "channel_id": config.CHANNEL_ID,
            "message_id": first_msg_id,
            "message_url": message_url,
        })
    return {"ok": True, "message_id": first_msg_id}


def _uncertain(position: int) -> dict:
    return {
        "ok": False,
        "error": f"Часть {position}: отправка начата, подтверждения нет. Требуется сверка с каналом.",
    }


def article_parts(body: str, image: str | None) -> list[tuple[str, str | None]]:
    """Plan the channel payload in the same order as the historical publication flow."""
    if not image:
        return [(part, None) for part in _split(body, TG_TEXT_LIMIT)]
    caption, tail = _caption_split(body)
    return [(caption, image), *((part, None) for part in _split(tail, TG_TEXT_LIMIT) if part.strip())]


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
