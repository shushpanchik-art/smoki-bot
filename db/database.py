import hashlib
import aiosqlite
import config

_SCHEMA_PATH = "/opt/SMOKI/bot/db/schema.sql"


async def init_db():
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.executescript(schema)
        await db.commit()


def topic_hash(title: str) -> str:
    norm = "".join(ch.lower() for ch in title if ch.isalnum())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


# ---------- published_topics ----------
async def get_used_topics(limit: int = 200) -> list[str]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "SELECT title FROM published_topics ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def add_topic(title: str, category: str, status: str = "draft") -> int:
    h = topic_hash(title)
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "INSERT OR IGNORE INTO published_topics (title, topic_hash, category, status) "
            "VALUES (?, ?, ?, ?)",
            (title, h, category, status),
        )
        await db.commit()
        if cur.lastrowid:
            return int(cur.lastrowid)
        cur = await db.execute(
            "SELECT id FROM published_topics WHERE topic_hash = ?", (h,)
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def set_topic_status(topic_id: int, status: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE published_topics SET status = ? WHERE id = ?", (status, topic_id)
        )
        await db.commit()


# ---------- articles ----------
async def add_article(topic_id: int, body: str, image_path: str | None = None,
                      image_prompt: str | None = None) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO articles (topic_id, body, image_path, image_prompt) "
            "VALUES (?, ?, ?, ?)",
            (topic_id, body, image_path, image_prompt),
        )
        await db.commit()
        return int(cur.lastrowid or 0)


async def get_article(article_id: int) -> dict | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def update_article(article_id: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [article_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(f"UPDATE articles SET {cols} WHERE id = ?", vals)
        await db.commit()


async def get_approved_article() -> dict | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM articles WHERE status = 'approved' ORDER BY id ASC LIMIT 1"
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_latest_pending_article() -> dict | None:
    """Последняя статья на модерации (для дедлайн-автопубликации)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM articles WHERE status IN ('pending', 'approved') "
            "ORDER BY id DESC LIMIT 1"
        )
        row = await cur.fetchone()
        return dict(row) if row else None


# ---------- comments ----------
async def add_comment(chat_id: int, message_id: int, user_id: int,
                      username: str, text: str) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO comments (chat_id, message_id, user_id, username, text) "
                "VALUES (?, ?, ?, ?, ?)",
                (chat_id, message_id, user_id, username, text),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_new_comments(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM comments WHERE status = 'new' ORDER BY id ASC LIMIT ?",
            (limit,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def update_comment(comment_id: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [comment_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(f"UPDATE comments SET {cols} WHERE id = ?", vals)
        await db.commit()


# ---------- ai_logs ----------
async def log_ai(kind: str, model: str, input_tokens: int = 0,
                 output_tokens: int = 0, images: int = 0, est_cost_usd: float = 0.0):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO ai_logs (kind, model, input_tokens, output_tokens, images, est_cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (kind, model, input_tokens, output_tokens, images, est_cost_usd),
        )
        await db.commit()


# ---------- settings (редактируемые правила и т.п.) ----------
async def get_setting(key: str, default: str | None = None) -> str | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value, updated_at) "
            "VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = datetime('now')",
            (key, value),
        )
        await db.commit()
