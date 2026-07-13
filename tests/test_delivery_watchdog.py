"""R1: watchdog доставки — get_undelivered_today (tmp_db)."""
import pytest


@pytest.mark.asyncio
async def test_undelivered_today_empty(tmp_db):
    from db import database as db
    await db.init_db()
    assert await db.get_undelivered_today() == []


@pytest.mark.asyncio
async def test_undelivered_today_pending(tmp_db):
    from db import database as db
    await db.init_db()
    tid = await db.add_topic("t", category="article")
    aid = await db.add_article(tid, body="body")  # status=pending по умолчанию
    stuck = await db.get_undelivered_today()
    assert [a["id"] for a in stuck] == [aid]


@pytest.mark.asyncio
async def test_undelivered_excludes_published(tmp_db):
    from db import database as db
    await db.init_db()
    tid = await db.add_topic("t2", category="article")
    aid = await db.add_article(tid, body="body")
    await db.update_article(aid, status="published")
    assert await db.get_undelivered_today() == []
