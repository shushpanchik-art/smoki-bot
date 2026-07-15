"""Регресс: pending story-слот с уже проставленным message_id
не должен повторно попадать в due-выборку (иначе бот шлёт одно
и то же изображение на модерацию каждые 10 минут)."""
import pytest

from db import database as db


@pytest.mark.asyncio
async def test_due_pending_excludes_already_sent(tmp_db):
    await db.init_db()
    # слот отправлен на модерацию (message_id проставлен)
    async with db.aiosqlite.connect(db.config.DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO story_jobs (status, target, theme, message_id, "
            "publish_at) VALUES ('pending', 'channel', 1, 555, NULL)"
        )
        # слот ещё не отправлен (message_id NULL)
        await conn.execute(
            "INSERT INTO story_jobs (status, target, theme, message_id, "
            "publish_at) VALUES ('pending', 'channel', 2, NULL, NULL)"
        )
        await conn.commit()

    due = await db.get_due_pending_story_jobs("2999-01-01T00:00:00")
    ids_themes = {j["theme"] for j in due}
    # в выборку попал только неотправленный (theme=2), не отправленный ранее
    assert ids_themes == {2}, f"ожидали только тему 2, получили {ids_themes}"


@pytest.mark.asyncio
async def test_due_pending_ignores_non_pending(tmp_db):
    await db.init_db()
    async with db.aiosqlite.connect(db.config.DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO story_jobs (status, target, theme, message_id, "
            "publish_at) VALUES ('approved', 'channel', 3, NULL, NULL)"
        )
        await conn.commit()
    due = await db.get_due_pending_story_jobs("2999-01-01T00:00:00")
    assert due == []
