"""Тесты webhook notifications (моки, без реальных HTTP запросов)."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from services import webhooks

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def mock_config(monkeypatch):
    """Устанавливаем тестовые webhook URLs."""
    import config
    monkeypatch.setattr(config, "WEBHOOK_URLS", {
        "article_published": "https://hooks.slack.com/test/published",
        "moderation_needed": "https://hooks.slack.com/test/moderation",
        "generation_failed": "https://hooks.slack.com/test/failed",
    })


async def test_send_webhook_success():
    """Успешная отправка webhook возвращает True."""
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.__aenter__ = AsyncMock(return_value=fake_resp)
    fake_resp.__aexit__ = AsyncMock()

    fake_session = MagicMock()
    fake_session.post = MagicMock(return_value=fake_resp)
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock()

    with patch("aiohttp.ClientSession", return_value=fake_session):
        result = await webhooks.send_webhook("article_published", {
            "article_id": 123,
            "title": "Тестовая статья"
        })

    assert result is True


async def test_send_webhook_http_error():
    """HTTP 500 возвращает False."""
    fake_resp = MagicMock()
    fake_resp.status = 500
    fake_resp.__aenter__ = AsyncMock(return_value=fake_resp)
    fake_resp.__aexit__ = AsyncMock()

    fake_session = MagicMock()
    fake_session.post = MagicMock(return_value=fake_resp)
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock()

    with patch("aiohttp.ClientSession", return_value=fake_session):
        result = await webhooks.send_webhook("article_published", {
            "article_id": 123
        })

    assert result is False


async def test_send_webhook_not_configured(monkeypatch):
    """Webhook не настроен → возвращает False (тихий skip)."""
    import config
    monkeypatch.setattr(config, "WEBHOOK_URLS", {
        "article_published": "",  # пустая строка = не настроен
    })

    result = await webhooks.send_webhook("article_published", {"test": "data"})
    assert result is False


async def test_send_webhook_unknown_event():
    """Неизвестный event → возвращает False."""
    result = await webhooks.send_webhook("unknown_event", {"test": "data"})
    assert result is False
