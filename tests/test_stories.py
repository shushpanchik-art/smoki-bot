import services.stories as stories
from db import database as db


async def test_pick_theme_in_range():
    for _ in range(50):
        assert stories.pick_theme() in {1, 2, 3, 4, 5}


def test_daily_count_bounds():
    for _ in range(50):
        n = stories._daily_count(3, 7)
        assert 3 <= n <= 7


def test_slot_times_count_and_order():
    times = stories._slot_times(5)
    assert len(times) == 5
    assert times == sorted(times)


async def test_generate_channel_slot_writes_pending(tmp_db, monkeypatch):
    await db.init_db()

    async def fake_text(prompt, **kw):
        return "Короткий текст сторис 🚬"

    async def fake_image(prompt):
        return b"\x89PNG\r\n\x1a\nFAKE"

    monkeypatch.setattr(stories, "_text", fake_text)
    monkeypatch.setattr(stories, "_image", fake_image)

    jid = await stories.generate_channel_slot(theme=1,
                                              publish_at="2025-06-01T10:00:00")
    assert jid is not None
    job = await db.get_story_job(jid)
    assert job["target"] == "channel"
    assert job["status"] == "pending"
    assert job["theme"] == 1
    assert job["image_path"] and job["image_path"].endswith(".png")
    assert job["caption"]


async def test_generate_channel_slot_no_image_returns_none(tmp_db, monkeypatch):
    await db.init_db()

    async def fake_text(prompt, **kw):
        return "text"

    async def no_image(prompt):
        return None

    monkeypatch.setattr(stories, "_text", fake_text)
    monkeypatch.setattr(stories, "_image", no_image)

    jid = await stories.generate_channel_slot(theme=2)
    assert jid is None


async def test_generate_flood_slot_reuses_image(tmp_db, monkeypatch):
    await db.init_db()
    src = await db.add_story_job("channel", theme=4,
                                prompt_en="p", image_path="/tmp/a.png",
                                caption="old")
    await db.update_story_job(src, status="published")

    async def fake_text(prompt, **kw):
        return "Интересный факт про кальяны 💨"

    monkeypatch.setattr(stories, "_text", fake_text)

    jid = await stories.generate_flood_slot(publish_at="2025-06-01T12:00:00")
    assert jid is not None
    job = await db.get_story_job(jid)
    assert job["target"] == "flood"
    assert job["image_path"] == "/tmp/a.png"
    assert job["caption"]


async def test_generate_flood_slot_empty_pool(tmp_db, monkeypatch):
    await db.init_db()
    jid = await stories.generate_flood_slot()
    assert jid is None
