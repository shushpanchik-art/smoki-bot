"""Тесты БД: схема, все таблицы, topic_hash, CRUD тем."""
import aiosqlite

from db import database as db

EXPECTED_TABLES = {
    "published_topics", "articles", "comments", "ai_logs", "settings",
}


async def test_init_db_creates_all_tables(tmp_db):
    await db.init_db()
    async with aiosqlite.connect(tmp_db) as con:
        cur = await con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        rows = await cur.fetchall()
    tables = {r[0] for r in rows}
    assert EXPECTED_TABLES.issubset(tables), f"нет таблиц: {EXPECTED_TABLES - tables}"


def test_topic_hash_deterministic():
    assert db.topic_hash("Привет Мир") == db.topic_hash("Привет Мир")


def test_topic_hash_ignores_case_and_punctuation():
    assert db.topic_hash("Привет, Мир!") == db.topic_hash("приветмир")


def test_topic_hash_length():
    assert len(db.topic_hash("любая тема")) == 16


def test_topic_hash_different_for_different_titles():
    assert db.topic_hash("тема раз") != db.topic_hash("тема два")


async def test_add_topic_and_get_used(tmp_db):
    await db.init_db()
    tid = await db.add_topic("Тестовая тема", "news")
    assert tid > 0
    used = await db.get_used_topics()
    assert "Тестовая тема" in used


async def test_add_topic_duplicate_returns_same_id(tmp_db):
    await db.init_db()
    tid1 = await db.add_topic("Дубликат", "news")
    tid2 = await db.add_topic("дубликат", "curious")  # тот же hash
    assert tid1 == tid2
