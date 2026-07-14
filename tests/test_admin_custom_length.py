"""FSM: своя тема + длина в одном сообщении (U4, одношаговый контракт).

fb_custom_topic принимает тему и (опционально) длину в одном сообщении,
формирует length_hint через prompts.custom_words_rule и запускает генерацию.
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

    async def get_state(self):
        return self._state

    async def set_state(self, st):
        self._state = st

    async def clear(self):
        self._data = {}
        self._state = None


@pytest.mark.asyncio
async def test_custom_topic_with_length(monkeypatch):
    captured = {}

    async def fake_do(message, bot, fmt="", topic=None, length_hint=None):
        captured["topic"] = topic
        captured["length_hint"] = length_hint

    monkeypatch.setattr(admin, "_do_generate", fake_do)
    msg = _admin_msg(monkeypatch, "вред IQOS, 300 слов")
    state = _FakeState()

    await admin.fb_custom_topic(msg, bot=MagicMock(), state=state)

    assert captured["topic"] == "вред IQOS, 300 слов"
    assert "300" in captured["length_hint"]
    assert state._state is None  # state cleared


@pytest.mark.asyncio
async def test_custom_topic_no_length_uses_default(monkeypatch):
    captured = {}

    async def fake_do(message, bot, fmt="", topic=None, length_hint=None):
        captured["topic"] = topic
        captured["length_hint"] = length_hint

    monkeypatch.setattr(admin, "_do_generate", fake_do)
    msg = _admin_msg(monkeypatch, "Кальян и здоровье")
    state = _FakeState()

    await admin.fb_custom_topic(msg, bot=MagicMock(), state=state)

    assert captured["topic"] == "Кальян и здоровье"
    assert "150" in captured["length_hint"]  # дефолт


@pytest.mark.asyncio
async def test_custom_topic_dash_no_topic(monkeypatch):
    captured = {}

    async def fake_do(message, bot, fmt="", topic=None, length_hint=None):
        captured["topic"] = topic

    monkeypatch.setattr(admin, "_do_generate", fake_do)
    msg = _admin_msg(monkeypatch, "-")
    state = _FakeState()

    await admin.fb_custom_topic(msg, bot=MagicMock(), state=state)

    assert captured["topic"] is None
