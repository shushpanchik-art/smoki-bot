"""U8.2a — тесты персистентной паузы контентных задач."""
import pytest

from services import schedule_control as sc


@pytest.mark.asyncio
async def test_toggle_persists_and_restores(tmp_db):
    from db import database
    await database.init_db()

    # изначально пусто
    assert await sc.get_paused() == set()
    assert await sc.is_paused("daily_evening") is False

    # включаем паузу
    now = await sc.toggle_pause("daily_evening")
    assert now is True
    assert await sc.is_paused("daily_evening") is True
    assert await sc.get_paused() == {"daily_evening"}

    # переживает "рестарт" (значение в БД)
    raw = await database.get_setting(sc.SETTING_KEY)
    assert raw == "daily_evening"

    # снимаем паузу
    now = await sc.toggle_pause("daily_evening")
    assert now is False
    assert await sc.get_paused() == set()


@pytest.mark.asyncio
async def test_protected_jobs_ignored(tmp_db):
    from db import database
    await database.init_db()
    # сторожа/неизвестные не паузятся
    assert await sc.toggle_pause("heartbeat") is False
    assert await sc.toggle_pause("delivery_watchdog") is False
    assert await sc.toggle_pause("nonexistent") is False
    assert await sc.get_paused() == set()


@pytest.mark.asyncio
async def test_save_keeps_only_whitelisted_ordered(tmp_db):
    from db import database
    await database.init_db()
    await sc.toggle_pause("send_pending_stories")
    await sc.toggle_pause("daily_morning")
    # порядок в CSV = порядок PAUSABLE_JOBS, не порядок вставки
    raw = await database.get_setting(sc.SETTING_KEY)
    assert raw == "daily_morning,send_pending_stories"
