"""U8.2b — тесты override часа утренней/вечерней джобы."""
import pytest

from services import schedule_control as sc


@pytest.mark.asyncio
async def test_no_override_uses_config(tmp_db):
    import config
    from db import database
    await database.init_db()
    assert await sc.get_hour_override("daily_morning") is None
    assert await sc.effective_hour("daily_morning") == config.MORNING_START
    assert await sc.effective_hour("daily_evening") == config.EVENING_START


@pytest.mark.asyncio
async def test_set_hour_persists_and_effective(tmp_db):
    from db import database
    await database.init_db()
    got = await sc.set_hour("daily_morning", 9)
    assert got == 9
    assert await sc.get_hour_override("daily_morning") == 9
    assert await sc.effective_hour("daily_morning") == 9
    raw = await database.get_setting("time_daily_morning")
    assert raw == "9"


@pytest.mark.asyncio
async def test_hour_clamped_0_23(tmp_db):
    from db import database
    await database.init_db()
    assert await sc.set_hour("daily_evening", 30) == 23
    assert await sc.set_hour("daily_evening", -5) == 0


@pytest.mark.asyncio
async def test_uneditable_job_ignored(tmp_db):
    from db import database
    await database.init_db()
    # process_comments не в TIME_EDITABLE
    assert await sc.get_hour_override("process_comments") is None
    r = await sc.set_hour("process_comments", 5)
    # возвращает effective (config-based), ничего не пишет
    assert await database.get_setting("time_process_comments") is None
    assert isinstance(r, int)
