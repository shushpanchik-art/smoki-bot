"""Тесты helper-функций handlers/admin.py (покрытие чистой логики)."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import config
from handlers import admin


def test_is_admin_id_matches(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 777)
    assert admin._is_admin_id(777) is True
    assert admin._is_admin_id(1) is False


def test_is_admin_id_zero_disabled(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 0)
    assert admin._is_admin_id(0) is False
    assert admin._is_admin_id(123) is False


def test_is_admin_message(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 555)
    msg_ok = SimpleNamespace(from_user=SimpleNamespace(id=555))
    msg_bad = SimpleNamespace(from_user=SimpleNamespace(id=1))
    msg_none = SimpleNamespace(from_user=None)
    assert admin._is_admin(msg_ok) is True
    assert admin._is_admin(msg_bad) is False
    assert admin._is_admin(msg_none) is False


def test_cb_arg_extracts_int():
    cq = SimpleNamespace(data="approve:42")
    assert admin._cb_arg(cq) == 42


def test_cb_arg_none_raises():
    cq = SimpleNamespace(data=None)
    with pytest.raises((ValueError, IndexError)):
        admin._cb_arg(cq)


def test_bot_returns_bot():
    fake_bot = object()
    cq = SimpleNamespace(bot=fake_bot)
    assert admin._bot(cq) is fake_bot


def test_bot_none_asserts():
    cq = SimpleNamespace(bot=None)
    with pytest.raises(AssertionError):
        admin._bot(cq)


@pytest.mark.parametrize(
    "text,expected",
    [
        (None, True),
        ("", True),
        ("-", True),
        ("—", True),
        ("нет", True),
        (" SKIP ", True),
        ("пропустить", True),
        ("нормальный фидбек", False),
        ("да", False),
    ],
)
def test_is_skip(text, expected):
    assert admin._is_skip(text) is expected


def test_kb_builds_markup():
    kb = admin._kb(99)
    # InlineKeyboardMarkup имеет .inline_keyboard (список рядов)
    assert hasattr(kb, "inline_keyboard")
    flat = [btn for row in kb.inline_keyboard for btn in row]
    assert any("99" in (b.callback_data or "") for b in flat)


async def test_clear_markup_success():
    msg = MagicMock()
    msg.edit_reply_markup = AsyncMock()
    cq = SimpleNamespace(message=msg)
    await admin._clear_markup(cq)
    msg.edit_reply_markup.assert_awaited_once()


async def test_clear_markup_no_message():
    cq = SimpleNamespace(message=None)
    await admin._clear_markup(cq)  # не должно падать


async def test_clear_markup_swallows_error():
    msg = MagicMock()
    msg.edit_reply_markup = AsyncMock(side_effect=Exception("boom"))
    cq = SimpleNamespace(message=msg)
    await admin._clear_markup(cq)  # исключение проглатывается
    msg.edit_reply_markup.assert_awaited_once()
