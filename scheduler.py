import logging
import random

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import config
from db import database
from services import comments, content, publisher

logger = logging.getLogger("smoki.scheduler")

_scheduler: AsyncIOScheduler | None = None


async def _job_generate(bot):
    """Утренняя генерация черновика → отправка админу на модерацию."""
    from handlers import admin
    logger.info("Планировщик: старт генерации статьи")
    try:
        res = await content.generate_article()
        if not res.get("ok"):
            logger.warning("Генерация не удалась: %s", res.get("reason"))
            try:
                await bot.send_message(
                    config.ADMIN_CHAT_ID,
                    f"⚠️ Плановая генерация не прошла цензуру:\n{res.get('reason')}"
                )
            except Exception:
                logger.exception("Не смог уведомить админа")
            return
        await admin.send_for_moderation(bot, res["article_id"])
        logger.info("Статья #%s отправлена на модерацию", res["article_id"])
    except Exception:
        logger.exception("Ошибка в плановой генерации")


async def _job_deadline(bot):
    """Дедлайн окна публикации: если статья на модерации висит — публикуем сами."""
    logger.info("Планировщик: проверка дедлайна публикации")
    try:
        art = await database.get_latest_pending_article()
        if not art:
            logger.info("Дедлайн: нет статей на модерации — пропуск")
            return
        aid = art["id"]
        res = await publisher.publish_article(bot, aid)
        if res.get("ok"):
            logger.info("Дедлайн: статья #%s опубликована автоматически", aid)
            try:
                await bot.send_message(
                    config.ADMIN_CHAT_ID,
                    f"⏰ Статья #{aid} опубликована автоматически "
                    f"(истёк срок модерации)."
                )
            except Exception:
                pass
        else:
            logger.warning("Дедлайн: ошибка публикации #%s: %s", aid, res.get("error"))
    except Exception:
        logger.exception("Ошибка в дедлайн-джобе")


async def _job_comments(bot):
    """Модерация новых комментариев в группе-обсуждении."""
    logger.info("Планировщик: обработка комментариев")
    try:
        stats = await comments.process_new_comments(bot)
        logger.info("Комментарии обработаны: %s", stats)
    except Exception:
        logger.exception("Ошибка в джобе модерации комментариев")


def _random_minute() -> int:
    return random.randint(0, 59)


def start(bot) -> AsyncIOScheduler:
    """Запуск планировщика. Вызывать после создания bot в main()."""
    global _scheduler
    if _scheduler:
        return _scheduler

    sched = AsyncIOScheduler(timezone="Europe/Moscow")

    # Генерация: случайная минута в начальный час окна генерации
    gen_min = _random_minute()
    sched.add_job(
        _job_generate,
        CronTrigger(hour=config.GEN_WINDOW_START, minute=gen_min),
        args=[bot],
        id="daily_generate",
        replace_existing=True,
    )
    logger.info("Джоб генерации: %02d:%02d", config.GEN_WINDOW_START, gen_min)

    # Дедлайн-автопубликация: конец окна публикации (последняя минута)
    sched.add_job(
        _job_deadline,
        CronTrigger(hour=config.PUBLISH_WINDOW_END, minute=0),
        args=[bot],
        id="publish_deadline",
        replace_existing=True,
    )
    logger.info("Джоб дедлайна публикации: %02d:00", config.PUBLISH_WINDOW_END)

    # Модерация комментариев: интервал COMMENTS_INTERVAL_HOURS
    sched.add_job(
        _job_comments,
        IntervalTrigger(hours=config.COMMENTS_INTERVAL_HOURS),
        args=[bot],
        id="process_comments",
        replace_existing=True,
    )
    logger.info("Джоб модерации комментариев: каждые %d ч",
                config.COMMENTS_INTERVAL_HOURS)

    sched.start()
    _scheduler = sched
    logger.info("Планировщик запущен")
    return sched
