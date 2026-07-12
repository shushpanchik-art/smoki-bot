"""Тест db.get_stats(): корректная сводка на temp-БД."""
from db import database as db


async def test_get_stats_empty_db(tmp_db):
    await db.init_db()
    s = await db.get_stats()
    assert s["published"] == 0
    assert s["pending"] == 0
    assert s["rejected"] == 0
    assert s["topics"] == 0
    assert s["comments_replied"] == 0
    assert s["comments_deleted"] == 0
    assert s["ai_calls"] == 0
    assert s["last_published"] is None


async def test_get_stats_counts_topics(tmp_db):
    await db.init_db()
    await db.add_topic("Тема для статистики", "news")
    s = await db.get_stats()
    assert s["topics"] == 1
    assert set(s) == {
        "published", "pending", "rejected",
        "topics", "comments_replied", "comments_deleted",
        "ai_calls", "last_published",
    }
