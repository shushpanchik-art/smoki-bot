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


async def apply_persisted_pauses() -> None:
    """Применить сохранённые паузы к планировщику при старте бота."""
    paused = await get_paused()
    if not paused:
        return
    for job_id in paused:
        if job_id in PAUSABLE_JOBS:
            _apply_to_live(job_id, True)
    logger.info("Восстановлены паузы из settings: %s", ", ".join(sorted(paused)))
