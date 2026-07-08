"""Тесты планировщика: регистрация джобов и вспомогательные функции."""
from unittest.mock import MagicMock

import scheduler


def _reset():
    scheduler._scheduler = None


def test_random_minute_in_range():
    for _ in range(100):
        assert 0 <= scheduler._random_minute() <= 59


def test_start_registers_two_jobs(monkeypatch):
    _reset()
    monkeypatch.setattr(scheduler.AsyncIOScheduler, "start", lambda self: None)
    sched = scheduler.start(MagicMock())
    ids = {j.id for j in sched.get_jobs()}
    assert "daily_generate" in ids
    assert "publish_deadline" in ids
    _reset()


def test_start_is_singleton(monkeypatch):
    _reset()
    monkeypatch.setattr(scheduler.AsyncIOScheduler, "start", lambda self: None)
    bot = MagicMock()
    first = scheduler.start(bot)
    second = scheduler.start(bot)
    assert first is second
    _reset()
