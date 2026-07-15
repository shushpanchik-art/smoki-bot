"""U8.4 — тесты экрана «Расписания» (services/schedule_view)."""
from datetime import datetime, timedelta, timezone

import pytest

from services import schedule_view as sv

MSK = timezone(timedelta(hours=3))

RAW_TIMERS = (
    "NEXT                        LEFT        LAST"
    "                        PASSED    UNIT"
    "                            ACTIVATES\n"
    "Wed 2026-07-15 17:15:00 MSK 42min left  "
    "Wed 2026-07-15 16:15:38 MSK 14min ago "
    "smoki-heartbeat.timer           smoki-heartbeat.service\n"
    "Mon 2026-07-20 04:21:09 MSK 4 days left -"
    "                           -         "
    "smoki-backup-restore-test.timer smoki-backup-restore-test.service\n"
    "\n2 timers listed.\n"
    "Pass --all to see loaded but inactive timers, too.\n"
)


class _FakeJob:
    def __init__(self, jid, nxt):
        self.id = jid
        self.next_run_time = nxt


def test_parse_systemd_multi_token_left():
    rows = sv.parse_systemd_timers(RAW_TIMERS)
    assert len(rows) == 2
    units = {r[0] for r in rows}
    assert units == {"smoki-heartbeat.timer",
                     "smoki-backup-restore-test.timer"}
    m = {r[0]: (r[1], r[2]) for r in rows}
    assert m["smoki-heartbeat.timer"] == ("2026-07-15 17:15:00", "42min")
    # многотокенный LEFT собран целиком
    assert m["smoki-backup-restore-test.timer"][1] == "4 days"


def test_parse_systemd_empty():
    assert sv.parse_systemd_timers("") == []
    assert sv.parse_systemd_timers("0 timers listed.\n") == []


def test_format_apscheduler_sort_and_labels():
    now = datetime(2026, 7, 15, 12, 0, tzinfo=MSK)
    jobs = [
        _FakeJob("heartbeat", now + timedelta(hours=2)),
        _FakeJob("daily_morning", now + timedelta(minutes=10)),
        _FakeJob("paused_job", None),
    ]
    out = sv.format_apscheduler(jobs)
    # известные подписи подставлены
    assert "Утренний пост" in out
    assert "Heartbeat" in out
    # ближайшая джоба (morning) идёт раньше heartbeat
    assert out.index("Утренний пост") < out.index("Heartbeat")
    # неизвестный id на паузе — в конце, показан как id
    assert "paused_job" in out
    assert out.index("Heartbeat") < out.index("paused_job")


def test_format_apscheduler_empty():
    assert "не запущен" in sv.format_apscheduler([])


def test_format_systemd_empty():
    assert "не найдены" in sv.format_systemd([])


@pytest.mark.asyncio
async def test_build_schedule_text(monkeypatch):
    now = datetime(2026, 7, 15, 12, 0, tzinfo=MSK)

    class _FakeSched:
        def get_jobs(self):
            return [_FakeJob("daily_morning", now + timedelta(hours=1))]

    import scheduler
    monkeypatch.setattr(scheduler, "get_scheduler", lambda: _FakeSched())

    async def _fake_read():
        return RAW_TIMERS
    monkeypatch.setattr(sv, "_read_systemd_timers", _fake_read)

    text = await sv.build_schedule_text()
    assert "<b>Расписания</b>" in text
    assert "Утренний пост" in text
    assert "Проверка heartbeat" in text
    assert "Тест восстановления" in text
    assert "4 days" in text
