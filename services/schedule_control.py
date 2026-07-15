"""U8.2a — управление паузой APScheduler-задач.

Пауза персистентна: список приостановленных job_id хранится в
settings["paused_jobs"] как CSV. При старте планировщика читается и
применяется (см. scheduler.apply_persisted_pauses). Тумблер в админ-панели
пишет в settings И сразу дёргает pause_job/resume_job — эффект мгновенный
и переживает рестарт бота.

Управляем ТОЛЬКО контентными джобами (белый список PAUSABLE_JOBS).
Сторожа heartbeat и delivery_watchdog не паузятся никогда.
"""
import logging

from db import database

logger = logging.getLogger("smoki.schedule_control")

SETTING_KEY = "paused_jobs"

# Белый список управляемых джоб: id -> человекочитаемая подпись.
# Порядок задаёт порядок кнопок в админ-панели.
PAUSABLE_JOBS: dict[str, str] = {
    "daily_morning": "\u2600\ufe0f Утренний",
    "daily_evening": "\U0001F319 Вечерний",
    "publish_deadline": "\u23F0 Дедлайн (день)",
    "publish_deadline_evening": "\u23F0 Дедлайн (вечер)",
    "process_comments": "\U0001F4AC Комментарии",
    "plan_stories_channel": "\U0001F4F8 Сторис (канал)",
    "plan_stories_flood": "\U0001F4F8 Сторис (флуд)",
    "send_pending_stories": "\U0001F4E4 Отправка сторис",
}


async def get_paused() -> set[str]:
    """Прочитать множество приостановленных job_id из settings."""
    raw = await database.get_setting(SETTING_KEY, "") or ""
    return {j for j in (x.strip() for x in raw.split(",")) if j}


async def _save_paused(paused: set[str]) -> None:
    # Сохраняем только валидные (из белого списка) в стабильном порядке.
    ordered = [j for j in PAUSABLE_JOBS if j in paused]
    await database.set_setting(SETTING_KEY, ",".join(ordered))


async def is_paused(job_id: str) -> bool:
    return job_id in await get_paused()


async def toggle_pause(job_id: str) -> bool:
    """Переключить паузу джобы. Возвращает новое состояние: True=на паузе.

    Пишет в settings и сразу применяет к живому планировщику.
    Небелые id игнорируются (защита от паузы сторожей).
    """
    if job_id not in PAUSABLE_JOBS:
        logger.warning("toggle_pause: неизвестный/защищённый job_id=%s", job_id)
        return False

    paused = await get_paused()
    if job_id in paused:
        paused.discard(job_id)
        now_paused = False
    else:
        paused.add(job_id)
        now_paused = True
    await _save_paused(paused)

    _apply_to_live(job_id, now_paused)
    logger.info("Джоба %s -> %s", job_id, "ПАУЗА" if now_paused else "работает")
    return now_paused


def _apply_to_live(job_id: str, paused: bool) -> None:
    """Применить состояние к запущенному планировщику (если он есть)."""
    import scheduler
    sched = scheduler.get_scheduler()
    if sched is None:
        return
    try:
        if sched.get_job(job_id) is None:
            return
        if paused:
            sched.pause_job(job_id)
        else:
            sched.resume_job(job_id)
    except Exception:
        logger.exception("Не удалось применить паузу к джобе %s", job_id)


# --- U8.2b: изменение часа запуска утренней/вечерней джобы ---
# job_id -> (settings_key, config-атрибут с дефолтным часом)
TIME_EDITABLE: dict[str, tuple[str, str]] = {
    "daily_morning": ("time_daily_morning", "MORNING_START"),
    "daily_evening": ("time_daily_evening", "EVENING_START"),
}


async def get_hour_override(job_id: str) -> int | None:
    """Час из settings или None, если переопределения нет."""
    if job_id not in TIME_EDITABLE:
        return None
    key = TIME_EDITABLE[job_id][0]
    raw = await database.get_setting(key)
    if raw is None or raw == "":
        return None
    try:
        h = int(raw)
    except ValueError:
        return None
    return h if 0 <= h <= 23 else None


async def effective_hour(job_id: str) -> int:
    """Актуальный час: override из settings, иначе дефолт из config."""
    import config
    ov = await get_hour_override(job_id)
    if ov is not None:
        return ov
    if job_id not in TIME_EDITABLE:
        return 0
    return int(getattr(config, TIME_EDITABLE[job_id][1]))


async def set_hour(job_id: str, hour: int) -> int:
    """Сохранить час (0-23), применить к живому планировщику. Возврат нового часа."""
    if job_id not in TIME_EDITABLE:
        logger.warning("set_hour: неуправляемый job_id=%s", job_id)
        return await effective_hour(job_id)
    hour = max(0, min(23, hour))
    await database.set_setting(TIME_EDITABLE[job_id][0], str(hour))
    _reschedule_live(job_id, hour)
    logger.info("Час джобы %s -> %02d:00", job_id, hour)
    return hour


def _reschedule_live(job_id: str, hour: int) -> None:
    """Перевесить cron живой джобы на новый час (минуту берём случайную)."""
    import random
    import scheduler
    from apscheduler.triggers.cron import CronTrigger
    sched = scheduler.get_scheduler()
    if sched is None or sched.get_job(job_id) is None:
        return
    try:
        sched.reschedule_job(
            job_id, trigger=CronTrigger(hour=hour, minute=random.randint(0, 59))
        )
    except Exception:
        logger.exception("Не удалось перевесить джобу %s", job_id)


async def apply_persisted_pauses() -> None:
    """Применить сохранённые паузы к планировщику при старте бота."""
    paused = await get_paused()
    for job_id in paused:
        if job_id in PAUSABLE_JOBS:
            _apply_to_live(job_id, True)
    logger.info("Восстановлены паузы из settings: %s", ", ".join(sorted(paused)))
    # U8.2b: применить сохранённые часы утро/вечер к живым джобам
    for job_id in TIME_EDITABLE:
        ov = await get_hour_override(job_id)
        if ov is not None:
            _reschedule_live(job_id, ov)
            logger.info("Восстановлен час %s -> %02d:00", job_id, ov)

