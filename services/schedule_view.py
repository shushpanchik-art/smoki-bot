"""U8.1 — сбор и форматирование расписаний для админ-панели.

Два источника:
  * APScheduler-джобы (контент/сторис/комменты/heartbeat) — из scheduler;
  * systemd-таймеры бэкапов (smoki-*.timer) — из `systemctl list-timers`.
Только ПРОСМОТР. Редактирование/пауза — отдельные задачи (U8.2/U8.3).
"""
import asyncio
import logging

logger = logging.getLogger("smoki.schedule_view")

# Человекочитаемые имена джоб (id -> подпись). Неизвестные id
# показываются как есть — панель не падает на новых джобах.
JOB_LABELS: dict[str, str] = {
    "daily_morning": "\u2600\ufe0f Утренний пост",
    "daily_evening": "\U0001F319 Вечерний лонг-рид",
    "publish_deadline": "\u23F0 Дедлайн-автопубликация (день)",
    "publish_deadline_evening": "\u23F0 Дедлайн-автопубликация (вечер)",
    "preview_warn_day": "\U0001F514 Напоминание перед дедлайном (день)",
    "preview_warn_evening": "\U0001F514 Напоминание перед дедлайном (вечер)",
    "delivery_watchdog": "\U0001F6A8 Watchdog доставки в канал",
    "process_comments": "\U0001F4AC Обработка комментариев",
    "heartbeat": "\U0001F493 Heartbeat (я жив)",
    "plan_stories_channel": "\U0001F4F8 План сторис (канал)",
    "plan_stories_flood": "\U0001F4F8 План сторис (флуд-группа)",
    "send_pending_stories": "\U0001F4E4 Отправка сторис на модерацию",
}


def _fmt_next(dt) -> str:
    """Форматировать next_run_time (tz-aware, MSK) в 'ДД.ММ ЧЧ:ММ'."""
    if dt is None:
        return "— (на паузе / не запланировано)"
    try:
        return dt.strftime("%d.%m %H:%M")
    except Exception:
        return str(dt)


def format_apscheduler(jobs) -> str:
    """Секция APScheduler-джоб. jobs — итерируемое из get_jobs()."""
    lines: list[str] = []
    items = []
    for job in jobs:
        label = JOB_LABELS.get(job.id, job.id)
        nxt = getattr(job, "next_run_time", None)
        items.append((nxt, label, job.id))
    # сортируем по ближайшему запуску; None (пауза) — в конец
    items.sort(key=lambda x: (x[0] is None, x[0] or 0))
    for nxt, label, _jid in items:
        lines.append(f"  {label}\n     \u2192 {_fmt_next(nxt)}")
    if not lines:
        return "  (планировщик не запущен или задач нет)"
    return "\n".join(lines)


def parse_systemd_timers(raw: str) -> list[tuple[str, str, str]]:
    """Разобрать вывод `systemctl list-timers`.

    Возвращает список (unit, next_str, left_str). Заголовок и хвост
    ('N timers listed.', пустые строки) отбрасываются.
    """
    result: list[tuple[str, str, str]] = []
    for line in raw.splitlines():
        line = line.rstrip()
        if not line or "UNIT" in line and "NEXT" in line:
            continue
        if "timers listed" in line or line.startswith("Pass "):
            continue
        # столбцы фикс. ширины; надёжнее выдернуть по маркерам.
        # формат: NEXT(дата время tz) LEFT LAST(дата время tz) PASSED UNIT ACT
        parts = line.split()
        if "smoki-" not in line:
            continue
        # найти UNIT (единственный токен, оканчивающийся .timer)
        unit = next((p for p in parts if p.endswith(".timer")), "")
        if not unit:
            continue
        # NEXT = первые 3 токена если это дата, иначе '-'
        if parts[0] == "-":
            next_str, left_str = "—", "—"
        else:
            next_str = " ".join(parts[0:3])  # 'Wed 2026-07-15 16:15:00 MSK' -> 3 токена без tz
            # LEFT — токен(ы) после NEXT(4 токена с tz) ... берём аккуратно:
            # NEXT занимает 4 токена (день, дата, время, tz)
            next_str = " ".join(parts[1:3])  # 'ДАТА ВРЕМЯ' без дня недели и tz
            # LEFT = токены после NEXT(4: день,дата,время,tz) до слова 'left'
            tail = parts[4:]
            if "left" in tail:
                left_str = " ".join(tail[:tail.index("left")]) or "—"
            else:
                left_str = tail[0] if tail else "—"
        result.append((unit, next_str, left_str))
    return result


TIMER_LABELS: dict[str, str] = {
    "smoki-heartbeat.timer": "\U0001F493 Проверка heartbeat",
    "smoki-backup.timer": "\U0001F4BE Локальный бэкап",
    "smoki-backup-offsite.timer": "\u2601\ufe0f Бэкап offsite",
    "smoki-backup-full-offsite.timer": "\u2601\ufe0f Полный бэкап offsite",
    "smoki-backup-summary.timer": "\U0001F4CB Сводка по бэкапам",
    "smoki-backup-restore-test.timer": "\U0001F9EA Тест восстановления",
}


def format_systemd(timers: list[tuple[str, str, str]]) -> str:
    if not timers:
        return "  (таймеры не найдены)"
    lines: list[str] = []
    for unit, next_str, left in timers:
        label = TIMER_LABELS.get(unit, unit)
        lines.append(f"  {label}\n     \u2192 {next_str} (\u0447\u0435\u0440\u0435\u0437 {left})")
    return "\n".join(lines)


async def _read_systemd_timers() -> str:
    """Асинхронно вызвать systemctl list-timers для smoki-*."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "list-timers", "smoki-*", "--no-pager",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        return out.decode("utf-8", "replace")
    except Exception:
        logger.exception("schedule_view: не удалось прочитать systemd-таймеры")
        return ""


async def build_schedule_text() -> str:
    """Собрать полный текст экрана «Расписания» для админ-панели."""
    import scheduler
    sched = scheduler.get_scheduler()
    jobs = sched.get_jobs() if sched else []
    aps = format_apscheduler(jobs)

    raw = await _read_systemd_timers()
    timers = parse_systemd_timers(raw)
    sysd = format_systemd(timers)

    return (
        "\U0001F5D3 <b>Расписания</b>\n"
        "<i>Время — MSK. Только просмотр.</i>\n\n"
        "\U0001F916 <b>Задачи бота (APScheduler):</b>\n"
        f"{aps}\n\n"
        "\u2699\ufe0f <b>Системные таймеры (бэкапы):</b>\n"
        f"{sysd}"
    )
