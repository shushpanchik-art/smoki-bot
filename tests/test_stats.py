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
    assert s["comments_total"] == 0
    assert s["comments_new"] == 0
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
        "comments_total", "comments_new",
        "ai_calls", "last_published",
    }


async def test_get_stats_counts_comments(tmp_db):
    """comments_total считает ВСЕ полученные, new — ожидающие обработки."""
    await db.init_db()
    await db.add_comment(-100, 1, 111, "user1", "первый коммент")
    await db.add_comment(-100, 2, 222, "user2", "второй коммент")
    await db.add_comment(-100, 3, 333, "user3", "третий коммент")
    # один отвечен, один удалён, один остаётся new
    await db.update_comment(1, status="replied")
    await db.update_comment(2, status="deleted")
    s = await db.get_stats()
    assert s["comments_total"] == 3
    assert s["comments_replied"] == 1
    assert s["comments_deleted"] == 1
    assert s["comments_new"] == 1
