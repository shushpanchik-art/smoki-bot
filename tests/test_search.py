"""Тесты поиска через Serper API (моки, без реальных запросов)."""
from unittest.mock import AsyncMock, MagicMock
import pytest

from ai import search

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def reset_session(monkeypatch):
    """Сброс синглтона сессии между тестами."""
    monkeypatch.setattr(search, "_session", None)


@pytest.fixture(autouse=True)
def mock_api_key(monkeypatch):
    """Устанавливаем тестовый ключ для всех тестов."""
    import config
    monkeypatch.setattr(config, "SERPER_API_KEY", "test-key")


async def test_search_news_returns_results(monkeypatch):
    """Успешный поиск возвращает список новостей."""
    fake_data = {
        "news": [
            {"title": "Новость 1", "link": "https://ex.com/1",
             "snippet": "Текст 1", "source": "Источник 1", "date": "2026-10-13"},
            {"title": "Новость 2", "link": "https://ex.com/2",
             "snippet": "Текст 2", "source": "Источник 2", "date": "2026-10-12"},
        ]
    }

    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.json = AsyncMock(return_value=fake_data)
    fake_resp.__aenter__ = AsyncMock(return_value=fake_resp)
    fake_resp.__aexit__ = AsyncMock()

    fake_session = MagicMock()
    fake_session.post = MagicMock(return_value=fake_resp)

    monkeypatch.setattr(search, "_get_session", lambda: fake_session)

    results = await search.search_news("вейп новости")
    assert len(results) == 2
    assert results[0]["title"] == "Новость 1"
    assert results[0]["source"] == "Источник 1"


async def test_search_news_no_api_key(monkeypatch):
    """Без SERPER_API_KEY возвращает None (fallback на grounding)."""
    import config
    monkeypatch.setattr(config, "SERPER_API_KEY", "")

    results = await search.search_news("query")
    assert results is None


async def test_search_news_handles_500(monkeypatch):
    """HTTP 500 → пустой список (fallback на grounding)."""
    fake_resp = MagicMock()
    fake_resp.status = 500
    fake_resp.__aenter__ = AsyncMock(return_value=fake_resp)
    fake_resp.__aexit__ = AsyncMock()

    fake_session = MagicMock()
    fake_session.post = MagicMock(return_value=fake_resp)

    monkeypatch.setattr(search, "_get_session", lambda: fake_session)

    results = await search.search_news("query")
    assert results == []


async def test_search_news_missing_news_key(monkeypatch):
    """Нет ключа 'news' в ответе → пустой список."""
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.json = AsyncMock(return_value={"error": "no results"})
    fake_resp.__aenter__ = AsyncMock(return_value=fake_resp)
    fake_resp.__aexit__ = AsyncMock()

    fake_session = MagicMock()
    fake_session.post = MagicMock(return_value=fake_resp)

    monkeypatch.setattr(search, "_get_session", lambda: fake_session)

    results = await search.search_news("query")
    assert results == []


def test_format_news_context():
    """Форматирование новостей для промпта."""
    news = [
        {"title": "Заголовок 1", "snippet": "Описание 1",
         "source": "Источник 1", "date": "2026-10-13", "link": ""},
        {"title": "Заголовок 2", "snippet": "Описание 2",
         "source": "Источник 2", "date": "2026-10-12", "link": ""},
    ]

    context = search.format_news_context(news)
    assert "Заголовок 1" in context
    assert "Источник 1, 2026-10-13" in context
    assert "Описание 1" in context


def test_format_news_context_empty():
    """Пустой список → пустая строка."""
    assert search.format_news_context([]) == ""
