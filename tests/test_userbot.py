"""U6.5 — тесты userbot.process_due_stories (публикация мокается)."""
import pytest

import userbot
from db import database


@pytest.mark.asyncio
async def test_publishes_approved_due(tmp_db, monkeypatch):
    await database.init_db()
    jid = await database.add_story_job(
        target="channel", image_path="/tmp/a.png",
        caption="факт", publish_at="2000-01-01T00:00:00+00:00",
    )
    await database.update_story_job(jid, status="approved")

    calls = {}

    async def fake_publish(client, job):
        calls["job_id"] = int(job["id"])
        return 777

    monkeypatch.setattr(userbot, "_publish_story", fake_publish)
    n = await userbot.process_due_stories(client=object())

    assert n == 1
    assert calls["job_id"] == jid
    row = await database.get_story_job(jid)
    assert row["status"] == "published"
    assert row["story_msg_id"] == 777


@pytest.mark.asyncio
async def test_skips_when_no_due(tmp_db, monkeypatch):
    await database.init_db()
    # pending — не approved: publish не должен вызываться
    await database.add_story_job(
        target="channel", image_path="/tmp/a.png", caption="x")

    async def boom(client, job):
        raise AssertionError("не должно вызываться")

    monkeypatch.setattr(userbot, "_publish_story", boom)
    assert await userbot.process_due_stories(client=object()) == 0


@pytest.mark.asyncio
async def test_error_marks_status_error(tmp_db, monkeypatch):
    await database.init_db()
    jid = await database.add_story_job(
        target="channel", image_path="/tmp/a.png",
        caption="x", publish_at="2000-01-01T00:00:00+00:00",
    )
    await database.update_story_job(jid, status="approved")

    async def boom(client, job):
        raise RuntimeError("api down")

    monkeypatch.setattr(userbot, "_publish_story", boom)
    n = await userbot.process_due_stories(client=object())

    assert n == 0
    row = await database.get_story_job(jid)
    assert row["status"] == "error"


def test_extract_story_id_variants():
    class _Story:
        id = 42

    class _Upd:
        story = _Story()

    class _Res:
        updates = [_Upd()]

    assert userbot._extract_story_id(_Res()) == 42

    class _Flat:
        id = 9
        updates = None

    assert userbot._extract_story_id(_Flat()) == 9

    class _None:
        updates = None
        id = None

    assert userbot._extract_story_id(_None()) is None
