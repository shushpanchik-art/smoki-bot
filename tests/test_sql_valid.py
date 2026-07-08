"""SQL-валидация: весь schema.sql должен исполняться в чистой SQLite.

Дешевле и надёжнее sqlfluff для диалекта SQLite: любая опечатка
или битый DDL в новых таблицах уронит тест сразу, без ложных
срабатываний линтера на 'IF NOT EXISTS' и datetime('now').
"""
import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def test_schema_file_exists():
    assert SCHEMA.is_file(), f"schema.sql not found at {SCHEMA}"


def test_schema_executes_cleanly():
    sql = SCHEMA.read_text(encoding="utf-8")
    assert sql.strip(), "schema.sql is empty"
    conn = sqlite3.connect(":memory:")
    try:
        # foreign_keys включаем, чтобы поймать битые REFERENCES
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(sql)  # упадёт при любом синтаксическом браке
        conn.commit()
    finally:
        conn.close()


def test_schema_is_idempotent():
    """Повторное исполнение не должно падать (все CREATE — IF NOT EXISTS)."""
    sql = SCHEMA.read_text(encoding="utf-8")
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(sql)
        conn.executescript(sql)  # второй прогон
        conn.commit()
    finally:
        conn.close()


def test_all_creates_use_if_not_exists():
    """Дисциплина: каждый CREATE TABLE должен быть IF NOT EXISTS."""
    sql = SCHEMA.read_text(encoding="utf-8").upper()
    creates = sql.count("CREATE TABLE")
    guarded = sql.count("CREATE TABLE IF NOT EXISTS")
    assert creates == guarded, (
        f"{creates - guarded} CREATE TABLE без IF NOT EXISTS — "
        "нарушает идемпотентность init_db()"
    )
