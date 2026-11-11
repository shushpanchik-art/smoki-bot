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


@pytest.mark.asyncio
@pytest.mark.parametrize("now_utc,day_start,day_end", [
    ("2026-11-10T20:59:59+00:00", "2026-11-09 21:00:00", "2026-11-10 21:00:00"),
    ("2026-11-10T21:00:00+00:00", "2026-11-10 21:00:00", "2026-11-11 21:00:00"),
    ("2026-11-11T00:20:00+00:00", "2026-11-10 21:00:00", "2026-11-11 21:00:00"),
    ("2027-01-01T00:20:00+00:00", "2026-12-31 21:00:00", "2027-01-01 21:00:00"),
])
async def test_delivery_day_uses_moscow_boundaries(tmp_db, monkeypatch, now_utc,
                                                day_start, day_end):
    from datetime import datetime, timedelta
    from db import database as db

    frozen = datetime.fromisoformat(now_utc)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is not None, "The delivery day must use an explicit timezone"
            return frozen.astimezone(tz)

    monkeypatch.setattr(db, "datetime", FixedDatetime)
    await db.init_db()
    start = datetime.fromisoformat(day_start)
    end = datetime.fromisoformat(day_end)
    cases = [
        (start - timedelta(seconds=1), "pending", False),
        (start, "pending", True),
        (start + timedelta(hours=3), "approved", True),
        (end - timedelta(seconds=1), "pending", True),
        (end, "pending", False),
        (start, "published", False),
        (start, "rejected", False),
    ]
    expected = []
    for index, (created_at, status, included) in enumerate(cases):
        topic = await db.add_topic(f"boundary-{index}", category="article")
        article = await db.add_article(topic, body="body")
        await db.update_article(article, created_at=created_at.strftime("%Y-%m-%d %H:%M:%S"),
                                status=status)
        if included:
            expected.append(article)
    assert [article["id"] for article in await db.get_undelivered_today()] == expected
