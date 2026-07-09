"""Проверка, что init_db создаёт все таблицы и ключевые колонки."""
import asyncio
import sqlite3


_EXPECTED = {
    "published_topics": {"id", "title", "topic_hash", "category", "status", "created_at"},
    "articles": {"id", "topic_id", "body", "image_path", "status", "message_id"},
    "comments": {"id", "chat_id", "message_id", "user_id", "text", "status"},
    "ai_logs": {"id", "kind", "model", "input_tokens", "output_tokens", "images"},
    "settings": {"key", "value"},
}


def _init(tmp_db):
    from db import database as db
    asyncio.run(db.init_db())


def test_all_tables_created(tmp_db):
    _init(tmp_db)
    con = sqlite3.connect(tmp_db)
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    con.close()
    for t in _EXPECTED:
        assert t in tables, f"таблица {t} не создана"


def test_columns_present(tmp_db):
    _init(tmp_db)
    con = sqlite3.connect(tmp_db)
    for table, cols in _EXPECTED.items():
        actual = {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
        missing = cols - actual
        assert not missing, f"{table}: нет колонок {missing}"
    con.close()


def test_init_db_idempotent(tmp_db):
    """Повторный init_db не падает (CREATE IF NOT EXISTS)."""
    _init(tmp_db)
    _init(tmp_db)
