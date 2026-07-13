"""FSM: своя тема + своя длина (U4).

fb_custom_topic сохраняет тему и переходит в waiting_custom_length;
fb_custom_length парсит число слов в length_hint и запускает генерацию.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers import admin


def _admin_msg(monkeypatch, text: str):
    monkeypatch.setattr(admin, "_is_admin", lambda m: True)
    msg = MagicMock()
    msg.text = text
    msg.answer = AsyncMock()
    return msg


class _FakeState:
    def __init__(self):
        self._data = {}
        self._state = None

    async def update_data(self, **kw):
        self._data.update(kw)

    async def get_data(self):
        return dict(self._data)

    async def set_state(self, st):
        self._state = st

    async def clear(self):
        self._data = {}
        self._state = None


@pytest.mark.asyncio
async def test_custom_topic_asks_length(monkeypatch):
    msg = _admin_msg(monkeypatch, "Кальян и здоровье")
    state = _FakeState()

    await admin.fb_custom_topic(msg, state)

    assert state._data["custom_topic"] == "Кальян и здоровье"
    assert state._state is admin.ModerationStates.waiting_custom_length
    msg.answer.assert_awaited()


@pytest.mark.asyncio
async def test_custom_topic_dash_no_topic(monkeypatch):
    msg = _admin_msg(monkeypatch, "-")
    state = _FakeState()

    await admin.fb_custom_topic(msg, state)

    assert state._data["custom_topic"] is None


@pytest.mark.asyncio
async def test_custom_length_number_builds_hint(monkeypatch):
    captured = {}

    async def fake_do(message, bot, fmt="", topic=None, length_hint=None):
        captured["topic"] = topic
        captured["length_hint"] = length_hint

    monkeypatch.setattr(admin, "_do_generate", fake_do)

    msg = _admin_msg(monkeypatch, "300")
    state = _FakeState()
    state._data["custom_topic"] = "Табак"

    await admin.fb_custom_length(msg, MagicMock(), state)

    assert captured["topic"] == "Табак"
    assert captured["length_hint"] is not None
    assert "300" in captured["length_hint"]
    assert state._state is None  # state cleared


@pytest.mark.asyncio
async def test_custom_length_dash_default_hint(monkeypatch):
    captured = {}

    async def fake_do(message, bot, fmt="", topic=None, length_hint=None):
        captured["length_hint"] = length_hint

    monkeypatch.setattr(admin, "_do_generate", fake_do)

    msg = _admin_msg(monkeypatch, "-")
    state = _FakeState()
    state._data["custom_topic"] = "X"

    await admin.fb_custom_length(msg, MagicMock(), state)

    assert captured["length_hint"] is None
