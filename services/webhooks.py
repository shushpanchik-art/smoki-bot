"""Webhook notifications для внешних сервисов (Discord, Slack, etc).

U13 — Интеграция с внешними системами через HTTP webhooks.
Отправка уведомлений о важных событиях:
- article_published — статья опубликована в канале
- moderation_needed — черновик отправлен на модерацию
- generation_failed — ошибка генерации контента

Конфигурация через WEBHOOK_URLS в config.py (опционально).
Если webhook не настроен — тихо skip, без ошибок.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any

import aiohttp

import config

logger = logging.getLogger("smoki.webhooks")


async def send_webhook(event: str, payload: dict[str, Any]) -> bool:
    """Отправить webhook-уведомление на внешний сервис.

    Args:
        event: Тип события ("article_published", "moderation_needed", "generation_failed")
        payload: Данные события (article_id, title, error, etc.)

    Returns:
        True если успешно отправлено, False если webhook не настроен или ошибка

    Example:
        await send_webhook("article_published", {
            "article_id": 123,
            "title": "Заголовок статьи",
            "channel_id": -1001234567890,
            "message_url": "https://t.me/channel/456"
        })
    """
    url = config.WEBHOOK_URLS.get(event)
    if not url:
        logger.debug(f"Webhook {event} не настроен, skip")
        return False

    data = {
        "event": event,
        "timestamp": datetime.now().isoformat(),
        "payload": payload
    }

    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                url,
                json=data,
                headers={"Content-Type": "application/json"}
            ) as resp:
                if resp.status >= 400:
                    logger.warning(f"Webhook {event} failed: HTTP {resp.status}")
                    return False

        logger.info(f"Webhook {event} отправлен: {url[:30]}...")
        return True

    except asyncio.TimeoutError:
        logger.warning(f"Webhook {event} timeout после 5 сек")
        return False
    except Exception as e:
        logger.warning(f"Webhook {event} ошибка: {e}")
        return False
