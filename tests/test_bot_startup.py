"""Startup must preserve queued updates without contacting Telegram in tests."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

import bot as entrypoint
from services import schedule_control


@pytest.fixture
def startup(monkeypatch):
    instance = Mock()
    instance.get_me = AsyncMock(
        return_value=SimpleNamespace(username="test_bot", id=123)
    )
    instance.delete_webhook = AsyncMock()
    dispatcher = Mock()
    dispatcher.start_polling = AsyncMock()
    events = Mock()
    events.attach_mock(instance.delete_webhook, "delete_webhook")
    events.attach_mock(dispatcher.start_polling, "start_polling")

    monkeypatch.setattr(entrypoint.config, "BOT_TOKEN", "123:TEST")
    monkeypatch.setattr(entrypoint, "Bot", Mock(return_value=instance))
    monkeypatch.setattr(entrypoint, "Dispatcher", Mock(return_value=dispatcher))
    monkeypatch.setattr(entrypoint.database, "init_db", AsyncMock())
    monkeypatch.setattr(entrypoint, "setup_bot_menu", AsyncMock())
    monkeypatch.setattr(entrypoint.scheduler, "start", Mock())
    monkeypatch.setattr(schedule_control, "apply_persisted_pauses", AsyncMock())
    return instance, dispatcher, events


@pytest.mark.asyncio
@pytest.mark.parametrize("starts", [1, 2])
async def test_start_and_restart_preserve_pending_updates(startup, starts):
    instance, dispatcher, events = startup
    for _ in range(starts):
        await entrypoint.main()

    assert instance.delete_webhook.await_args_list == [
        call(drop_pending_updates=False)
    ] * starts
    assert dispatcher.start_polling.await_args_list == [call(instance)] * starts
    assert events.mock_calls == [
        call.delete_webhook(drop_pending_updates=False),
        call.start_polling(instance),
    ] * starts


@pytest.mark.asyncio
async def test_webhook_failure_does_not_start_polling(startup):
    instance, dispatcher, _ = startup
    instance.delete_webhook.side_effect = RuntimeError("synthetic webhook failure")

    with pytest.raises(RuntimeError, match="synthetic webhook failure"):
        await entrypoint.main()

    instance.delete_webhook.assert_awaited_once_with(drop_pending_updates=False)
    dispatcher.start_polling.assert_not_awaited()
