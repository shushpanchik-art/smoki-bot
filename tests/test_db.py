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


async def test_add_and_get_article(tmp_db):
    await db.init_db()
    tid = await db.add_topic("Статья тема", "news")
    aid = await db.add_article(tid, "тело статьи", image_path="/img/a.jpg",
                               image_prompt="prompt text")
    assert aid > 0
    art = await db.get_article(aid)
    assert art is not None
    assert art["topic_id"] == tid
    assert art["body"] == "тело статьи"
    assert art["image_path"] == "/img/a.jpg"
    assert art["image_prompt"] == "prompt text"


async def test_add_article_minimal(tmp_db):
    await db.init_db()
    tid = await db.add_topic("Мин статья", "news")
    aid = await db.add_article(tid, "только тело")
    art = await db.get_article(aid)
    assert art is not None
    assert art["body"] == "только тело"
    assert art["image_path"] is None
    assert art["image_prompt"] is None


async def test_get_article_not_found(tmp_db):
    await db.init_db()
    assert await db.get_article(999999) is None


async def test_update_article_fields(tmp_db):
    await db.init_db()
    tid = await db.add_topic("Апдейт тема", "news")
    aid = await db.add_article(tid, "старое тело")
    await db.update_article(aid, body="новое тело", status="approved")
    art = await db.get_article(aid)
    assert art is not None
    assert art["body"] == "новое тело"
    assert art["status"] == "approved"


async def test_update_article_empty_noop(tmp_db):
    await db.init_db()
    tid = await db.add_topic("Ноуп тема", "news")
    aid = await db.add_article(tid, "тело")
    await db.update_article(aid)  # без полей — не должно падать
    art = await db.get_article(aid)
    assert art is not None
    assert art["body"] == "тело"


async def test_set_and_get_setting(tmp_db):
    await db.init_db()
    await db.set_setting("mykey", "value1")
    assert await db.get_setting("mykey") == "value1"


async def test_set_setting_upsert(tmp_db):
    await db.init_db()
    await db.set_setting("k", "first")
    await db.set_setting("k", "second")  # ON CONFLICT -> обновляет
    assert await db.get_setting("k") == "second"


async def test_get_setting_default(tmp_db):
    await db.init_db()
    assert await db.get_setting("absent") is None
    assert await db.get_setting("absent", "def") == "def"
