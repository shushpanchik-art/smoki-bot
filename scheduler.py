import logging
import random
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from aiogram import Bot

import config
from db import database
from ai import prompts
from services import comments, content, publisher

logger = logging.getLogger("smoki.scheduler")

_scheduler: AsyncIOScheduler | None = None
_bot: Bot | None = None


async def _generate_and_moderate(length_hint: str, label: str):
    from handlers import admin
    logger.info("Планировщик: старт генерации (%s)", label)
    assert _bot is not None
    bot = _bot
    try:
        res = await content.generate_article(length_hint=length_hint)
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


async def _job_morning():
    """Утро: 1-3 факта + остроумный коммент → модерация."""
    n = int(await database.get_setting("morning_facts",
                                       str(config.MORNING_LEN_DEFAULT)) or config.MORNING_LEN_DEFAULT)
    await _generate_and_moderate(prompts.facts_rules(n), "утро")


async def _job_evening():
    """Вечер: лонг-рид заданной длины → модерация."""
    w = int(await database.get_setting("evening_words",
                                       str(config.EVENING_WORDS_DEFAULT)) or config.EVENING_WORDS_DEFAULT)
    await _generate_and_moderate(prompts.words_rule(w), "вечер")


async def _job_deadline():
    """Дедлайн: публикуем ВСЕ зависшие на модерации статьи дня."""
    logger.info("Планировщик: проверка дедлайна публикации")
    assert _bot is not None
    bot = _bot
    try:
        stuck = await database.get_undelivered_today()
        if not stuck:
            logger.info("Дедлайн: нет статей на модерации — пропуск")
            return
        published: list[int] = []
        failed: list[int] = []
        for art in stuck:
            aid = art["id"]
            res = await publisher.publish_article(bot, aid)
            if res.get("ok"):
                published.append(aid)
                logger.info("Дедлайн: статья #%s опубликована автоматически", aid)
            else:
                failed.append(aid)
                logger.warning(
                    "Дедлайн: ошибка публикации #%s: %s", aid, res.get("error")
                )
        parts: list[str] = []
        if published:
            parts.append(
                "⏰ Опубликованы автоматически (истёк срок модерации): "
                + ", ".join(f"#{i}" for i in published)
            )
        if failed:
            parts.append(
                "⚠️ НЕ удалось опубликовать: "
                + ", ".join(f"#{i}" for i in failed)
            )
        if parts:
            try:
                await bot.send_message(config.ADMIN_CHAT_ID, "\n".join(parts))
            except Exception:
                pass
    except Exception:
        logger.exception("Ошибка в дедлайн-джобе")


async def _job_delivery_watchdog():
    """Watchdog доставки: если статья дня не опубликована — алерт админу.

    Запускается после окна публикации. Ловит случаи, когда publish_article
    вернул ok=False или дедлайн-джоба не отработала (простой службы).
    """
    logger.info("Планировщик: watchdog доставки")
    assert _bot is not None
    bot = _bot
    try:
        stuck = await database.get_undelivered_today()
        if not stuck:
            logger.info("Watchdog: все статьи дня доставлены — ок")
            return
        ids = ", ".join(f"#{a['id']}" for a in stuck)
        logger.warning("Watchdog: не опубликованы статьи дня: %s", ids)
        try:
            await bot.send_message(
                config.ADMIN_CHAT_ID,
                "⚠️ Watchdog доставки: статьи дня НЕ опубликованы в канал: "
                f"{ids}. Проверь модерацию/логи публикации.",
            )
        except Exception:
            logger.exception("Watchdog: не смог отправить алерт админу")
    except Exception:
        logger.exception("Ошибка в watchdog-джобе доставки")


async def _job_comments():
    """Модерация новых комментариев в группе-обсуждении."""
    logger.info("Планировщик: обработка комментариев")
    assert _bot is not None
    try:
        stats = await comments.process_new_comments(_bot)
        logger.info("Комментарии обработаны: %s", stats)
    except Exception:
        logger.exception("Ошибка в джобе модерации комментариев")


async def _job_heartbeat():
    """Heartbeat: доказательство живого scheduler-цикла.

    Пишет маркер "HEARTBEAT ok" в journald. Внешний systemd-timer
    (heartbeat_healthcheck.sh) грепает journald на свежесть маркера
    и алертит, если бот/планировщик завис (сам себя проверить не может).
    """
    logger.info("HEARTBEAT ok")


def _random_minute() -> int:
    return random.randint(0, 59)


def start(bot) -> AsyncIOScheduler:
    """Запуск планировщика. Вызывать после создания bot в main()."""
    global _scheduler, _bot
    if _scheduler:
        return _scheduler

    _bot = bot

    jobstores = {
        "default": SQLAlchemyJobStore(url=f"sqlite:///{config.DB_PATH}"),
    }

    sched = AsyncIOScheduler(
        timezone="Europe/Moscow",
        jobstores=jobstores,
        job_defaults={
            "misfire_grace_time": 3600,
            "coalesce": True,
            "max_instances": 1,
        },
    )

    # Утренний пост (факты): случайная минута в начале утреннего окна
    m_min = _random_minute()
    sched.add_job(
        _job_morning,
        CronTrigger(hour=config.MORNING_START, minute=m_min),
        id="daily_morning", replace_existing=True,
    )
    logger.info("Джоб утро: %02d:%02d", config.MORNING_START, m_min)

    # Вечерний пост (лонг-рид)
    e_min = _random_minute()
    sched.add_job(
        _job_evening,
        CronTrigger(hour=config.EVENING_START, minute=e_min),
        id="daily_evening", replace_existing=True,
    )
    logger.info("Джоб вечер: %02d:%02d", config.EVENING_START, e_min)

    # Дедлайн-автопубликация: конец окна публикации (последняя минута)
    sched.add_job(
        _job_deadline,
        CronTrigger(hour=config.PUBLISH_WINDOW_END, minute=0),
        id="publish_deadline",
        replace_existing=True,
    )
    logger.info("Джоб дедлайна публикации: %02d:00", config.PUBLISH_WINDOW_END)

    # Вечерний дедлайн: добить вечерний лонг-рид тем же вечером
    sched.add_job(
        _job_deadline,
        CronTrigger(
            hour=config.EVENING_DEADLINE_HOUR,
            minute=config.EVENING_DEADLINE_MINUTE,
        ),
        id="publish_deadline_evening",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )
    logger.info(
        "Джоб вечернего дедлайна: %02d:%02d",
        config.EVENING_DEADLINE_HOUR,
        config.EVENING_DEADLINE_MINUTE,
    )

    # Watchdog доставки: через 2 ч после окна публикации (но не позже 23:00)
    wd_hour = min(config.PUBLISH_WINDOW_END + 2, 23)
    sched.add_job(
        _job_delivery_watchdog,
        CronTrigger(hour=wd_hour, minute=0),
        id="delivery_watchdog",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )
    logger.info("Джоб watchdog доставки: %02d:00", wd_hour)

    # Модерация комментариев: интервал COMMENTS_INTERVAL_HOURS
    sched.add_job(
        _job_comments,
        IntervalTrigger(hours=config.COMMENTS_INTERVAL_HOURS),
        id="process_comments",
        replace_existing=True,
    )
    logger.info("Джоб модерации комментариев: каждые %d ч",
                config.COMMENTS_INTERVAL_HOURS)

    # Heartbeat: маркер живого scheduler-цикла каждые N часов
    sched.add_job(
        _job_heartbeat,
        IntervalTrigger(hours=config.HEARTBEAT_INTERVAL_HOURS),
        id="heartbeat",
        replace_existing=True,
        misfire_grace_time=1800,
        coalesce=True,
        next_run_time=datetime.now(),
    )
    logger.info("Джоб heartbeat: каждые %d ч",
                config.HEARTBEAT_INTERVAL_HOURS)

    sched.start()
    _scheduler = sched
    logger.info("Планировщик запущен (persistent jobstore: %s)", config.DB_PATH)
    return sched
