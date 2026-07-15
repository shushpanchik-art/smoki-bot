"""U6.5 — Telethon-userbot: публикация approved story-слотов как Stories.

Отдельный процесс (smoki-userbot.service), НЕ внутри aiogram-бота.
Связь с ботом через общую БД (таблица story_jobs).

Telethon импортируется ЛЕНИВО внутри функций — модуль можно импортировать
и тестировать без установленного telethon (публикация мокается).

Прод-запуск требует (ручной шаг U6.5b):
  - реальные TG_API_ID / TG_API_HASH / TG_USERBOT_PHONE в .env;
  - интерактивную авторизацию сессии (код из SMS) — первый запуск в TTY;
  - буст канала @SMOKTOLK до уровня доступности Stories (иначе ошибка прав).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import config
from db import database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("smoki-userbot")

# Период жизни Story в секундах (24 ч).
_STORY_PERIOD = 86400
# Как часто проверять approved-слоты (сек).
POLL_INTERVAL_SEC = 300


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _publish_story(client: Any, job: dict) -> int | None:
    """Публикует один слот как Story. Возвращает story_msg_id или None.

    Изолировано ради мокабельности в тестах. Telethon-объекты создаются
    здесь лениво, чтобы модуль импортировался без telethon.
    """
    from telethon.tl.functions.stories import SendStoryRequest
    from telethon.tl.types import InputMediaUploadedPhoto

    image_path = job.get("image_path")
    if not image_path:
        logger.warning("Story #%s без image_path — пропуск", job.get("id"))
        return None

    target = job.get("target")
    peer_str = (
        config.STORY_FLOOD_CHANNEL if target == "flood" else config.CHANNEL_ID
    )
    peer = await client.get_input_entity(peer_str)

    uploaded = await client.upload_file(image_path)
    media = InputMediaUploadedPhoto(file=uploaded)
    caption = job.get("caption") or ""

    result = await client(
        SendStoryRequest(
            peer=peer,
            media=media,
            caption=caption[:2048],
            period=_STORY_PERIOD,
        )
    )
    # Достаём id опубликованной истории (структура зависит от версии слоя).
    story_id = _extract_story_id(result)
    logger.info(
        "Story #%s опубликована в %s (story_id=%s)",
        job.get("id"), peer_str, story_id,
    )
    return story_id


def _extract_story_id(result: Any) -> int | None:
    """Пытается достать id истории из ответа SendStoryRequest."""
    updates = getattr(result, "updates", None)
    if updates:
        for upd in updates:
            story = getattr(upd, "story", None)
            sid = getattr(story, "id", None)
            if sid is not None:
                return int(sid)
    sid = getattr(result, "id", None)
    return int(sid) if sid is not None else None


async def process_due_stories(client: Any) -> int:
    """Публикует все approved-слоты с наступившим publish_at.

    Возвращает число успешно опубликованных. При ошибке отдельного слота
    ставит status='error' и продолжает (одна плохая история не роняет цикл).
    """
    jobs = await database.get_due_approved_story_jobs(_now_iso())
    if not jobs:
        return 0

    published = 0
    for job in jobs:
        job_id = int(job["id"])
        try:
            story_msg_id = await _publish_story(client, job)
        except Exception:
            logger.exception("Ошибка публикации story #%s", job_id)
            await database.update_story_job(job_id, status="error")
            continue

        if story_msg_id is None and not job.get("image_path"):
            await database.update_story_job(job_id, status="error")
            continue

        await database.update_story_job(
            job_id, status="published", story_msg_id=story_msg_id
        )
        published += 1

    if published:
        logger.info("Опубликовано историй: %s", published)
    return published


async def _build_client() -> Any:
    """Создаёт и подключает Telethon-клиент (прод). Требует .env + сессию."""
    from telethon import TelegramClient

    if not config.TG_API_ID or not config.TG_API_HASH:
        raise RuntimeError(
            "TG_API_ID/TG_API_HASH не заданы в .env — userbot не запустится"
        )
    client = TelegramClient(
        config.TG_SESSION_PATH, config.TG_API_ID, config.TG_API_HASH
    )
    await client.start(phone=config.TG_USERBOT_PHONE)  # type: ignore[arg-type]
    me = await client.get_me()
    logger.info("Userbot авторизован как %s", getattr(me, "username", me))
    return client


async def main() -> None:
    await database.init_db()
    client = await _build_client()
    logger.info("Userbot запущен, интервал опроса %s c", POLL_INTERVAL_SEC)
    try:
        while True:
            try:
                await process_due_stories(client)
            except Exception:
                logger.exception("Ошибка цикла публикации историй")
            await asyncio.sleep(POLL_INTERVAL_SEC)
    finally:
        await client.disconnect()  # type: ignore[union-attr]


if __name__ == "__main__":
    asyncio.run(main())
