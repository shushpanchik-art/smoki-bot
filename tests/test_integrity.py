"""Целостность данных: UNIQUE-констрейнты и дедупликация."""
import asyncio

import pytest


def _init(tmp_db):
    from db import database as db
    asyncio.run(db.init_db())


def test_duplicate_topic_returns_same_id(tmp_db):
    _init(tmp_db)
    from db import database as db
    id1 = asyncio.run(db.add_topic("Вейпы 2025", "news"))
    id2 = asyncio.run(db.add_topic("вейпы 2025", "news"))  # тот же после нормализации
    assert id1 == id2, "дубль темы должен вернуть тот же id"
    assert id1 > 0


def test_different_topics_different_ids(tmp_db):
    _init(tmp_db)
    from db import database as db
    id1 = asyncio.run(db.add_topic("Тема А", "news"))
    id2 = asyncio.run(db.add_topic("Тема Б", "science"))
    assert id1 != id2


def test_duplicate_comment_rejected(tmp_db):
    _init(tmp_db)
    from db import database as db
    ok1 = asyncio.run(db.add_comment(100, 5, 1, "user", "текст"))
    ok2 = asyncio.run(db.add_comment(100, 5, 1, "user", "текст"))  # тот же chat+msg
    assert ok1 is True
    assert ok2 is False, "дубль (chat_id, message_id) должен быть отклонён"


def test_different_comments_accepted(tmp_db):
    _init(tmp_db)
    from db import database as db
    ok1 = asyncio.run(db.add_comment(100, 5, 1, "user", "a"))
    ok2 = asyncio.run(db.add_comment(100, 6, 1, "user", "b"))
    assert ok1 is True and ok2 is True


def test_topic_hash_normalization():
    from db import database as db
    assert db.topic_hash("Привет, Мир!") == db.topic_hash("приветмир")
    assert db.topic_hash("A") != db.topic_hash("B")
