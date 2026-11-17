"""Durable, ordered Telegram delivery state for channel articles."""

import aiosqlite

import config


async def prepare(
    article_id: int, chat_id: str, parts: list[tuple[str, str | None]],
) -> list[aiosqlite.Row]:
    """Persist the original payload before any send and reuse it on resume."""
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("BEGIN IMMEDIATE")
        query = "SELECT * FROM article_publication_parts WHERE article_id = ? ORDER BY position"
        saved = list(await conn.execute_fetchall(query, (article_id,)))
        if saved:
            return saved

        eligible = await conn.execute_fetchall(
            "SELECT 1 FROM articles WHERE id = ? AND status IN ('pending', 'approved') "
            "AND message_id IS NULL", (article_id,),
        )
        if not eligible:
            return []

        await conn.executemany(
            "INSERT INTO article_publication_parts (article_id, position, chat_id, text, image_path) "
            "VALUES (?, ?, ?, ?, ?)",
            [(article_id, i, chat_id, text, image) for i, (text, image) in enumerate(parts, 1)],
        )
        saved = list(await conn.execute_fetchall(query, (article_id,)))
        await conn.commit()
        return saved


async def claim(article_id: int, position: int) -> bool:
    """Commit the uncertain state before issuing a request to Telegram."""
    async with aiosqlite.connect(config.DB_PATH) as conn:
        cur = await conn.execute(
            "UPDATE article_publication_parts SET state = 'uncertain', updated_at = datetime('now') "
            "WHERE article_id = ? AND position = ? AND state = 'pending' "
            "AND EXISTS (SELECT 1 FROM articles WHERE id = ? AND status IN ('pending', 'approved')) "
            "AND NOT EXISTS (SELECT 1 FROM article_publication_parts "
            "WHERE article_id = ? AND position < ? AND state != 'confirmed')",
            (article_id, position, article_id, article_id, position),
        )
        await conn.commit()
        return cur.rowcount == 1


async def resolve(article_id: int, position: int, message_id: int | None) -> None:
    """Confirm delivery, or release the claim after a definite rejection."""
    state = "pending" if message_id is None else "confirmed"
    async with aiosqlite.connect(config.DB_PATH) as conn:
        cur = await conn.execute(
            "UPDATE article_publication_parts SET state = ?, message_id = ?, "
            "updated_at = datetime('now') WHERE article_id = ? AND position = ? "
            "AND state = 'uncertain'",
            (state, message_id, article_id, position),
        )
        if cur.rowcount != 1:
            raise RuntimeError("Publication part has no outstanding claim")
        if position == 1 and message_id is not None:
            await conn.execute(
                "UPDATE articles SET message_id = ? WHERE id = ?", (message_id, article_id),
            )
        await conn.commit()


async def finish(article_id: int) -> tuple[int | None, bool]:
    """Finalize a fully confirmed article once. Return its first ID and whether it changed."""
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        cur = await conn.execute(
            "UPDATE articles SET status = 'published', published_at = datetime('now'), "
            "message_id = (SELECT message_id FROM article_publication_parts "
            "WHERE article_id = ? AND position = 1) "
            "WHERE id = ? AND status IN ('pending', 'approved') "
            "AND EXISTS (SELECT 1 FROM article_publication_parts "
            "WHERE article_id = ? AND position = 1 AND state = 'confirmed') "
            "AND NOT EXISTS (SELECT 1 FROM article_publication_parts "
            "WHERE article_id = ? AND state != 'confirmed') "
            "RETURNING message_id",
            (article_id, article_id, article_id, article_id),
        )
        row = await cur.fetchone()
        await cur.close()
        if row:
            await conn.execute(
                "UPDATE published_topics SET status = 'published' "
                "WHERE id = (SELECT topic_id FROM articles WHERE id = ?)", (article_id,),
            )
            await conn.commit()
            return int(row[0]), True
        cur = await conn.execute(
            "SELECT message_id FROM articles WHERE id = ? AND status = 'published' AND message_id > 0",
            (article_id,),
        )
        existing = await cur.fetchone()
        return (int(existing[0]) if existing else None), False
