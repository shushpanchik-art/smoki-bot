"""Поиск свежих новостей через Serper API."""
import logging
from typing import TypedDict

import aiohttp

import config

logger = logging.getLogger(__name__)

_session: aiohttp.ClientSession | None = None


class NewsItem(TypedDict):
    """Структура одной новости из Serper."""
    title: str
    snippet: str
    source: str
    date: str
    link: str


def _get_session() -> aiohttp.ClientSession:
    """Ленивая инициализация HTTP сессии (синглтон)."""
    global _session
    if _session is None:
        _session = aiohttp.ClientSession()
    return _session


async def close_session() -> None:
    """Закрыть HTTP сессию при завершении работы."""
    global _session
    if _session is not None:
        await _session.close()
        _session = None


async def search_news(query: str, *, days: int = 7,
                     num_results: int = 5) -> list[NewsItem] | None:
    """Поиск свежих новостей через Serper News API.

    Args:
        query: Поисковый запрос
        days: Последние N дней (default: 7)
        num_results: Количество результатов (default: 5, max: 10)

    Returns:
        list[NewsItem]: Список новостей с метаданными
        None: Если SERPER_API_KEY не задан (fallback на grounding)
        []: Пустой список при ошибке API (fallback на grounding)
    """
    if not config.SERPER_API_KEY:
        logger.debug("SERPER_API_KEY не задан, skip explicit search")
        return None

    url = "https://google.serper.dev/news"
    headers = {
        "X-API-KEY": config.SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "num": min(num_results, 10),
        "tbs": f"qdr:d{days}",
        "gl": "ru",
        "hl": "ru"
    }

    try:
        session = _get_session()
        async with session.post(url, json=payload, headers=headers,
                               timeout=aiohttp.ClientTimeout(total=10.0)) as resp:
            if resp.status != 200:
                logger.error("Serper API error: status=%d", resp.status)
                return []
            data = await resp.json()

        # Парсинг результатов
        news = []
        for item in data.get("news", []):
            news.append(NewsItem(
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                source=item.get("source", ""),
                date=item.get("date", ""),
                link=item.get("link", "")
            ))

        logger.info("Serper News: найдено %d результатов для '%s'",
                   len(news), query[:50])
        return news

    except Exception as e:  # noqa: BLE001
        logger.warning("Serper API ошибка (fallback на grounding): %s", e)
        return []  # Пустой список → сигнал использовать grounding


def format_news_context(news: list[NewsItem]) -> str:
    """Форматирование новостей для промпта Gemini.

    Args:
        news: Список новостей из search_news()

    Returns:
        Отформатированный текст для добавления в промпт или пустая строка
    """
    if not news:
        return ""

    lines = ["АКТУАЛЬНЫЕ НОВОСТИ ПО ТЕМЕ:\n"]
    for i, item in enumerate(news[:3], 1):  # Берём только топ-3
        if not item["title"]:
            continue
        lines.append(f"{i}. {item['title']}")
        if item["snippet"]:
            lines.append(f"   {item['snippet']}")
        if item["source"] and item["date"]:
            lines.append(f"   Источник: {item['source']}, {item['date']}\n")

    return "\n".join(lines)
