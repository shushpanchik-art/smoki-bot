"""Тесты heartbeat: джоба зарегистрирована и пишет маркер в лог."""
from unittest.mock import MagicMock

import scheduler


def _reset():
    scheduler._scheduler = None


def test_heartbeat_job_registered(monkeypatch):
    _reset()
    monkeypatch.setattr(scheduler.AsyncIOScheduler, "start", lambda self: None)
    sched = scheduler.start(MagicMock())
    ids = {j.id for j in sched.get_jobs()}
    assert "heartbeat" in ids
    _reset()


async def test_heartbeat_logs_marker(caplog):
    import logging

    with caplog.at_level(logging.INFO, logger=scheduler.logger.name):
        await scheduler._job_heartbeat()
    assert any("HEARTBEAT ok" in r.getMessage() for r in caplog.records)
