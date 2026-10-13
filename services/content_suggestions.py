"""Автоматические подсказки трендовых тем для статей.

U14 — Подсказки тем на основе:
1. Serper News API (уже подключен) — свежие новости
2. RSS-ленты тематических сайтов
3. Опционально: Google Trends API (будущее)

Каждое утро в 07:00 MSK отправляет админу топ-5 трендовых тем.
"""
import logging
from typing import List

import feedparser  # pip install feedparser

from ai import search as ai_search

logger = logging.getLogger("smoki.content_suggestions")

# RSS-ленты тематических сайтов (примеры, можно расширять)
RSS_FEEDS = [
    # Добавить реальные RSS при наличии
    # "https://vape.ru/rss",
    # "https://hookahrussia.ru/feed",
]


async def get_trending_topics(limit: int = 5) -> List[str]:
    """Собрать топ трендовых тем из разных источников.

    Args:
        limit: Максимальное количество тем для возврата

    Returns:
        Список тем (заголовки новостей, RSS записи)

    Example:
        topics = await get_trending_topics(5)
        # ["Новый закон о вейпах", "Запрет продажи одноразок", ...]
    """
    topics = []

    # 1. Serper News API — свежие новости (последние 1-2 дня)
    try:
        serper_results = await ai_search.search_news(
            query="вейп OR кальян OR электронные сигареты OR одноразки OR под-системы",
            days=2,
            num_results=5
        )

        if serper_results:
            for item in serper_results[:3]:  # топ-3 новости
                if item.get("title"):
                    topics.append(item["title"])
            logger.info("Serper News: добавлено %d тем", len([t for t in topics]))
    except Exception as e:
        logger.warning("Ошибка получения Serper News: %s", e)

    # 2. RSS-ленты (если настроены)
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:2]:  # топ-2 из каждого фида
                if hasattr(entry, "title") and entry.title:
                    topics.append(entry.title)
        except Exception as e:
            logger.warning("Ошибка парсинга RSS %s: %s", feed_url, e)

    # 3. Дедупликация и обрезка
    unique_topics = []
    seen_lower = set()
    for topic in topics:
        topic_lower = topic.lower()
        if topic_lower not in seen_lower:
            unique_topics.append(topic)
            seen_lower.add(topic_lower)

    return unique_topics[:limit]


def format_suggestions_message(topics: List[str]) -> str:
    """Форматировать список тем для отправки админу.

    Args:
        topics: Список тем

    Returns:
        Отформатированный текст сообщения
    """
    if not topics:
        return "📭 Трендовых тем на сегодня не найдено.\n\nИспользуй /post_custom для генерации статьи по своей теме."

    text = "🔥 <b>Трендовые темы на сегодня:</b>\n\n"
    for i, topic in enumerate(topics, 1):
        text += f"{i}. {topic}\n"

    text += "\n💡 Используй /post_custom <тема> для генерации статьи по любой из этих тем."

    return text
