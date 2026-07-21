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
    assert s["tokens_total"] == 0
    assert s["cost_total_usd"] == 0.0
    assert s["budget_usd"] == 0.0
    assert s["posts_left_est"] == 0
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
        "ai_calls", "tokens_total", "last_published",
        "cost_total_usd", "avg_cost_per_post_usd",
        "budget_usd", "posts_left_est",
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



async def test_get_stats_cost(tmp_db, monkeypatch):
    """U9a: cost_total_usd = токены/1M*прайс + картинки*прайс."""
    import config
    monkeypatch.setattr(config, "PRICE_TEXT_IN_USD_PER_1M", 1.0)
    monkeypatch.setattr(config, "PRICE_TEXT_OUT_USD_PER_1M", 2.0)
    monkeypatch.setattr(config, "PRICE_IMAGE_USD", 0.5)
    monkeypatch.setattr(config, "MONTHLY_BUDGET_USD", 0.0)
    await db.init_db()
    # 1M input, 500k output, 2 картинки
    await db.log_ai("text", "m", input_tokens=1_000_000,
                    output_tokens=500_000, images=2)
    s = await db.get_stats()
    # 1.0 + 1.0 + 1.0 = 3.0
    assert s["cost_total_usd"] == 3.0
