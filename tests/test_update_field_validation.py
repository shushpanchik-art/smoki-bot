"""Dynamic SQL identifiers are restricted to explicit schema allowlists."""
from unittest.mock import Mock

import aiosqlite
import pytest

import config
from db import database as db


UPDATES = [
    (db.update_article, (1,), "articles"),
    (db.update_comment, (1,), "comments"),
    (db.update_story_job, (1,), "story_jobs"),
    (db.upsert_saga_state, (), "saga_state"),
]


@pytest.mark.parametrize("update,args,table", UPDATES)
@pytest.mark.parametrize("field", ["unknown", "status = 'published' --", "body, status", "status\n", "status\"", "status; DROP TABLE articles; --"])
async def test_bad_identifiers_rejected_before_database_access(monkeypatch, update, args, table, field):
    connect = Mock(side_effect=AssertionError("Must validate before connecting"))
    monkeypatch.setattr(aiosqlite, "connect", connect)
    with pytest.raises(ValueError, match="Unsupported update fields"):
        await update(*args, **{field: "value"})
    connect.assert_not_called()


@pytest.mark.parametrize("update,args,table", UPDATES)
async def test_empty_updates_stay_noops(monkeypatch, update, args, table):
    connect = Mock(side_effect=AssertionError("Empty update should not connect"))
    monkeypatch.setattr(aiosqlite, "connect", connect)
    await update(*args)
    connect.assert_not_called()


async def test_allowlists_cover_schema_and_migrations(tmp_db):
    await db.init_db()
    async with aiosqlite.connect(config.DB_PATH) as conn:
        for table, allowed in db._UPDATE_COLUMNS.items():
            # Table names are fixed application constants, not test input.
            cur = await conn.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in await cur.fetchall()}
            if table == "saga_state":
                columns.remove("id")  # Singleton key is managed by upsert itself.
            assert allowed == columns


@pytest.mark.parametrize("update,args,table", UPDATES)
async def test_values_are_bound_and_all_valid_columns_remain_supported(tmp_db, update, args, table):
    await db.init_db()
    payload = "literal ' ; DROP TABLE articles; --"
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute("INSERT INTO articles (id, body) VALUES (1, 'original')")
        await conn.execute("INSERT INTO comments (id) VALUES (1)")
        await conn.execute("INSERT INTO story_jobs (id, target) VALUES (1, 'channel')")
        await conn.commit()
    # For saga this exercises INSERT first, then UPDATE, including migrated fields.
    for column in db._UPDATE_COLUMNS[table]:
        value = 1 if column == "id" else payload
        await update(*args, **{column: value})
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(f"SELECT * FROM {table} WHERE id = 1")
        row = await cur.fetchone()
        assert row is not None
        for column in db._UPDATE_COLUMNS[table]:
            if column not in {"id", "updated_at"}:
                assert row[column] == payload
        cur = await conn.execute("SELECT count(*) FROM articles")
        assert (await cur.fetchone())[0] == 1
