"""Джоба модерации комментариев в группе-обсуждении (FR-6).

Раз в COMMENTS_INTERVAL_HOURS берёт новые комментарии, классифицирует
через AI и выполняет действие: удалить (reklama/toxic) или ответить
(question/neutral/positive). Ошибки Telegram не роняют джобу.
"""
import asyncio
import logging

import config
from ai import gemini, prompts
from db import database as db

logger = logging.getLogger("smoki.comments")

CATEGORIES = {"reklama", "toxic", "question", "neutral", "positive"}
DELETE_CATS = {"reklama", "toxic"}


async def _classify(text: str) -> str:
    """Классифицировать комментарий → одна из 5 категорий (fallback neutral)."""
    raw = await asyncio.to_thread(
        gemini.generate_text,
        prompts.classify_comment_prompt(text),
        temperature=0.2,
        max_output_tokens=16,
    )
    try:
        await db.log_ai("text", config.GEMINI_TEXT_MODEL,
                        input_tokens=len(text) // 4,
                        output_tokens=len(raw) // 4)
    except Exception:
        logger.exception("log_ai classify")
    # Защита: нижний регистр, первое слово, whitelist.
    word = (raw or "").strip().lower().split()[0] if raw.strip() else ""
    word = word.strip(".,!:;-—«»\"'")
    return word if word in CATEGORIES else "neutral"


async def _reply(text: str, category: str) -> str:
    """Сгенерировать ответ на комментарий."""
    out = await asyncio.to_thread(
        gemini.generate_text,
        prompts.reply_comment_prompt(text, category),
        temperature=0.9,
        max_output_tokens=512,
    )
    try:
        await db.log_ai("text", config.GEMINI_TEXT_MODEL,
                        input_tokens=len(text) // 4,
                        output_tokens=len(out) // 4)
    except Exception:
        logger.exception("log_ai reply")
    return (out or "").strip()


async def process_new_comments(bot) -> dict[str, int]:
    """Обработать все новые комментарии. Возвращает статистику."""
    stats = {"processed": 0, "deleted": 0, "replied": 0, "errors": 0}
    comments = await db.get_new_comments(limit=50)
    for c in comments:
        cid = c["id"]
        chat_id = c["chat_id"]
        message_id = c["message_id"]
        text = c.get("text") or ""
        stats["processed"] += 1
        try:
            category = await _classify(text)
        except Exception:
            logger.exception("Ошибка классификации #%s", cid)
            await db.update_comment(cid, status="error",
                                    processed_at=_now())
            stats["errors"] += 1
            continue

        try:
            if category in DELETE_CATS:
                await bot.delete_message(chat_id, message_id)
                await db.update_comment(cid, status="deleted",
                                        classification=category,
                                        bot_reply=None, processed_at=_now())
                stats["deleted"] += 1
            else:
                reply = await _reply(text, category)
                await bot.send_message(chat_id, reply,
                                       reply_to_message_id=message_id)
                await db.update_comment(cid, status="replied",
                                        classification=category,
                                        bot_reply=reply, processed_at=_now())
                stats["replied"] += 1
        except Exception:
            logger.exception("Ошибка действия #%s (cat=%s)", cid, category)
            await db.update_comment(cid, status="error",
                                    classification=category,
                                    processed_at=_now())
            stats["errors"] += 1

    logger.info("Модерация комментов: %s", stats)
    return stats


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
