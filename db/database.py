import hashlib
import aiosqlite
import config

_SCHEMA_PATH = "/opt/SMOKI/bot/db/schema.sql"


async def init_db():
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.executescript(schema)
        await _migrate_saga(db)
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
                      image_prompt: str | None = None,
                      length_hint: str | None = None) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO articles (topic_id, body, image_path, image_prompt, "
            "length_hint) VALUES (?, ?, ?, ?, ?)",
            (topic_id, body, image_path, image_prompt, length_hint),
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


async def get_article_length_hint(article_id: int) -> str | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "SELECT length_hint FROM articles WHERE id = ?", (article_id,))
        row = await cur.fetchone()
        return row[0] if row and row[0] else None


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


async def get_undelivered_today() -> list[dict]:
    """Статьи, созданные сегодня, но НЕ опубликованные (для watchdog доставки).

    Возвращает статьи в статусе pending/approved с created_at за текущую дату.
    Пустой список = всё доставлено (или контента дня ещё не было).
    """
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM articles "
            "WHERE status IN ('pending', 'approved') "
            "AND date(created_at) = date('now', 'localtime') "
            "ORDER BY id ASC"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


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
# ===== U-saga: saga_state + saga_summaries =====

async def _migrate_saga(db) -> None:
    """Идемпотентно добавляет новые колонки saga_state в старых БД."""
    cur = await db.execute("PRAGMA table_info(saga_state)")
    cols = {row[1] for row in await cur.fetchall()}
    add = {
        "narration": "TEXT",
        "last_tail": "TEXT",
        "pending_arc_seed": "TEXT",
        "arc_status": "TEXT DEFAULT 'in_progress'",
        "arc_synopsis_json": "TEXT DEFAULT '[]'",
        "prev_first_message_id": "INTEGER",
    }
    for name, decl in add.items():
        if name not in cols:
            await db.execute(
                f"ALTER TABLE saga_state ADD COLUMN {name} {decl}")
    await db.commit()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS saga_posts (
          id INTEGER PRIMARY KEY,
          arc_number INTEGER NOT NULL,
          episode_in_arc INTEGER NOT NULL,
          part_index INTEGER NOT NULL,
          message_id INTEGER NOT NULL,
          is_first INTEGER DEFAULT 0,
          is_last INTEGER DEFAULT 0,
          deleted INTEGER DEFAULT 0,
          created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    await db.commit()


async def get_saga_state() -> dict | None:
    """Единственная строка состояния саги (id=1) или None если ещё нет."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM saga_state WHERE id = 1")
        row = await cur.fetchone()
        return dict(row) if row else None


async def upsert_saga_state(**fields) -> None:
    """Создаёт (id=1) или обновляет строку состояния саги."""
    if not fields:
        return
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM saga_state WHERE id = 1")
        exists = await cur.fetchone()
        if exists:
            cols = ", ".join(f"{k} = ?" for k in fields)
            cols += ", updated_at = datetime('now')"
            vals = list(fields.values()) + [1]
            await db.execute(
                f"UPDATE saga_state SET {cols} WHERE id = ?", vals)
        else:
            keys = ["id"] + list(fields.keys())
            marks = ", ".join("?" for _ in keys)
            vals = [1] + list(fields.values())
            await db.execute(
                f"INSERT INTO saga_state ({', '.join(keys)}) "
                f"VALUES ({marks})", vals)
        await db.commit()


async def add_saga_summary(episode_number: int, arc_number: int,
                           summary: str) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO saga_summaries (episode_number, arc_number, summary) "
            "VALUES (?, ?, ?)",
            (episode_number, arc_number, summary),
        )
        await db.commit()


async def get_saga_summaries() -> list[dict]:
    """ВСЕ саммари всех эпизодов по порядку — полная память саги."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM saga_summaries ORDER BY episode_number ASC")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def add_saga_posts(arc_number: int, episode_in_arc: int,
                         message_ids: list[int]) -> None:
    """Журналирует все части опубликованного эпизода саги."""
    if not message_ids:
        return
    n = len(message_ids)
    async with aiosqlite.connect(config.DB_PATH) as db:
        for idx, mid in enumerate(message_ids):
            await db.execute(
                "INSERT INTO saga_posts (arc_number, episode_in_arc, "
                "part_index, message_id, is_first, is_last) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (arc_number, episode_in_arc, idx, mid,
                 1 if idx == 0 else 0, 1 if idx == n - 1 else 0),
            )
        await db.commit()


async def get_saga_posts(include_deleted: bool = False) -> list[dict]:
    """Весь журнал постов саги по порядку (arc, episode, part)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        q = "SELECT * FROM saga_posts"
        if not include_deleted:
            q += " WHERE deleted = 0"
        q += " ORDER BY arc_number ASC, episode_in_arc ASC, part_index ASC"
        cur = await db.execute(q)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_saga_episodes() -> list[dict]:
    """Живые эпизоды журнала: по одной записи на эпизод с first/last msg_id."""
    posts = await get_saga_posts(include_deleted=False)
    by_ep: dict[tuple[int, int], dict] = {}
    for row in posts:
        key = (row["arc_number"], row["episode_in_arc"])
        ep = by_ep.setdefault(key, {
            "arc_number": row["arc_number"],
            "episode_in_arc": row["episode_in_arc"],
            "first_message_id": None,
            "last_message_id": None,
            "parts": 0,
        })
        ep["parts"] += 1
        if row["is_first"]:
            ep["first_message_id"] = row["message_id"]
        if row["is_last"]:
            ep["last_message_id"] = row["message_id"]
    return [by_ep[k] for k in sorted(by_ep)]


async def mark_saga_episode_deleted(arc_number: int,
                                    episode_in_arc: int) -> None:
    """Помечает все части эпизода как удалённые (фантом/пропал из канала)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE saga_posts SET deleted = 1 "
            "WHERE arc_number = ? AND episode_in_arc = ?",
            (arc_number, episode_in_arc),
        )
        await db.commit()


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


async def append_setting(key: str, text: str, sep: str = "\n- ", limit: int = 4000):
    """Накопительно дописать строку в settings[key] (для фидбэка/цензуры)."""
    text = (text or "").strip()
    if not text:
        return
    old = await get_setting(key, "") or ""
    combined = (old + sep + text) if old else text
    if len(combined) > limit:
        combined = combined[-limit:]
    await set_setting(key, combined)


async def get_recent_comments(limit: int = 10) -> list[dict]:
    """Последние N комментов (любого статуса) для админ-панели."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, username, text, status, classification, bot_reply "
            "FROM comments ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ---------- статистика для админ-панели ----------
async def get_stats() -> dict:
    """Сводка для админ-панели: счётчики статей/тем/комментов/ИИ-вызовов."""
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        async def _one(sql: str, args: tuple = ()) -> int:
            cur = await conn.execute(sql, args)
            row = await cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0

        published = await _one(
            "SELECT COUNT(*) FROM articles WHERE status = 'published'")
        pending = await _one(
            "SELECT COUNT(*) FROM articles WHERE status = 'pending'")
        rejected = await _one(
            "SELECT COUNT(*) FROM articles WHERE status = 'rejected'")
        topics = await _one("SELECT COUNT(*) FROM published_topics")
        comments_replied = await _one(
            "SELECT COUNT(*) FROM comments WHERE status = 'replied'")
        comments_deleted = await _one(
            "SELECT COUNT(*) FROM comments WHERE status = 'deleted'")
        comments_total = await _one("SELECT COUNT(*) FROM comments")
        comments_new = await _one(
            "SELECT COUNT(*) FROM comments WHERE status = 'new'")
        ai_calls = await _one("SELECT COUNT(*) FROM ai_logs")
        tokens_total = await _one(
            "SELECT COALESCE(SUM(input_tokens), 0) "
            "+ COALESCE(SUM(output_tokens), 0) FROM ai_logs")

        async def _sum(sql: str, args: tuple = ()) -> float:
            cur = await conn.execute(sql, args)
            row = await cur.fetchone()
            return float(row[0]) if row and row[0] is not None else 0.0

        # U9a: оценка стоимости AI по прайсу из config
        in_tok = await _sum("SELECT COALESCE(SUM(input_tokens), 0) FROM ai_logs")
        out_tok = await _sum(
            "SELECT COALESCE(SUM(output_tokens), 0) FROM ai_logs")
        img_cnt = await _sum("SELECT COALESCE(SUM(images), 0) FROM ai_logs")
        cost_total = (
            in_tok / 1_000_000 * config.PRICE_TEXT_IN_USD_PER_1M
            + out_tok / 1_000_000 * config.PRICE_TEXT_OUT_USD_PER_1M
            + img_cnt * config.PRICE_IMAGE_USD
        )
        budget = config.MONTHLY_BUDGET_USD
        avg_cost_post = (cost_total / published) if published else 0.0
        posts_left = 0
        if budget > 0 and avg_cost_post > 0:
            posts_left = max(0, int((budget - cost_total) / avg_cost_post))

        cur = await conn.execute(
            "SELECT published_at FROM articles "
            "WHERE status = 'published' AND published_at IS NOT NULL "
            "ORDER BY published_at DESC LIMIT 1")
        row = await cur.fetchone()
        last_published = row[0] if row and row[0] else None

    return {
        "published": published,
        "pending": pending,
        "rejected": rejected,
        "topics": topics,
        "comments_replied": comments_replied,
        "comments_deleted": comments_deleted,
        "comments_total": comments_total,
        "comments_new": comments_new,
        "ai_calls": ai_calls,
        "tokens_total": tokens_total,
        "cost_total_usd": round(cost_total, 4),
        "avg_cost_per_post_usd": round(avg_cost_post, 4),
        "budget_usd": round(budget, 2),
        "posts_left_est": posts_left,
        "last_published": last_published,
    }


# ===== U6: story_jobs (авто-Stories, userbot) =====

async def add_story_job(target: str, theme: int | None = None,
                        prompt_en: str | None = None,
                        image_path: str | None = None,
                        caption: str | None = None,
                        publish_at: str | None = None) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO story_jobs (target, theme, prompt_en, image_path, "
            "caption, publish_at) VALUES (?, ?, ?, ?, ?, ?)",
            (target, theme, prompt_en, image_path, caption, publish_at),
        )
        await db.commit()
        return int(cur.lastrowid or 0)


async def get_story_job(job_id: int) -> dict | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM story_jobs WHERE id = ?", (job_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def update_story_job(job_id: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [job_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            f"UPDATE story_jobs SET {cols} WHERE id = ?", vals)
        await db.commit()


async def get_due_approved_story_jobs(now_iso: str) -> list[dict]:
    """approved-задачи, у которых publish_at <= now (для userbot)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM story_jobs WHERE status = 'approved' "
            "AND (publish_at IS NULL OR publish_at <= ?) ORDER BY id ASC",
            (now_iso,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_pending_story_jobs() -> list[dict]:
    """pending-задачи, ожидающие approve-flow в боте."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM story_jobs WHERE status = 'pending' "
            "ORDER BY id ASC"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_due_pending_story_jobs(now_iso: str) -> list[dict]:
    """pending-слоты с наступившим publish_at (для отправки на модерацию)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM story_jobs WHERE status = 'pending' "
            "AND message_id IS NULL "
            "AND (publish_at IS NULL OR publish_at <= ?) ORDER BY id ASC",
            (now_iso,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_published_story_images(limit: int = 200) -> list[dict]:
    """Готовые картинки для реюза во flood (status=published, есть image_path)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM story_jobs WHERE status = 'published' "
            "AND image_path IS NOT NULL ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
