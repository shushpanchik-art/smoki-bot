"""U4: FSM уточнения длины своей темы (waiting_custom_length).

Проверяем цепочку fb_custom_topic -> waiting_custom_length -> fb_custom_length:
переход состояния, парсинг числа в words_rule и передачу length_hint в
_do_generate.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import config
from ai import prompts
from handlers import admin
from handlers.admin import ModerationStates


class _FakeState:
    """Минимальный FSMContext: хранит state и data в памяти."""

    def __init__(self, data=None):
        self._state = None
        self._data = dict(data or {})

    async def get_state(self):
        return self._state

    async def set_state(self, state):
        self._state = state

    async def update_data(self, **kw):
        self._data.update(kw)

    async def get_data(self):
        return dict(self._data)

    async def clear(self):
        self._state = None
        self._data = {}


@pytest.mark.asyncio
async def test_fb_custom_topic_moves_to_length(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 555)
    state = _FakeState()
    msg = SimpleNamespace(
        from_user=SimpleNamespace(id=555),
        text="вейпы и здоровье",
        answer=AsyncMock(),
    )
    await admin.fb_custom_topic(msg, state)
    # тема сохранена, состояние переключено на ожидание длины
    assert (await state.get_data())["custom_topic"] == "вейпы и здоровье"
    assert await state.get_state() == ModerationStates.waiting_custom_length
    msg.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_fb_custom_topic_dash_means_random(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 555)
    state = _FakeState()
    msg = SimpleNamespace(
        from_user=SimpleNamespace(id=555), text="-", answer=AsyncMock()
    )
    await admin.fb_custom_topic(msg, state)
    assert (await state.get_data())["custom_topic"] is None
    assert await state.get_state() == ModerationStates.waiting_custom_length


@pytest.mark.asyncio
async def test_fb_custom_length_number_sets_hint(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 555)
    captured = {}

    async def fake_do_generate(message, bot, mode, topic=None, length_hint=None):
        captured["topic"] = topic
        captured["length_hint"] = length_hint

    monkeypatch.setattr(admin, "_do_generate", fake_do_generate)
    state = _FakeState({"custom_topic": "тест"})
    await state.set_state(ModerationStates.waiting_custom_length)
    msg = SimpleNamespace(from_user=SimpleNamespace(id=555), text="350")
    await admin.fb_custom_length(msg, bot=object(), state=state)

    assert captured["topic"] == "тест"
    assert captured["length_hint"] == prompts.words_rule(350)
    # состояние очищено после генерации
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_fb_custom_length_dash_means_default(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 555)
    captured = {}

    async def fake_do_generate(message, bot, mode, topic=None, length_hint=None):
        captured["length_hint"] = length_hint

    monkeypatch.setattr(admin, "_do_generate", fake_do_generate)
    state = _FakeState({"custom_topic": None})
    await state.set_state(ModerationStates.waiting_custom_length)
    msg = SimpleNamespace(from_user=SimpleNamespace(id=555), text="-")
    await admin.fb_custom_length(msg, bot=object(), state=state)

    assert captured["length_hint"] is None


@pytest.mark.asyncio
async def test_fb_custom_length_non_admin_ignored(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 555)
    called = {"n": 0}

    async def fake_do_generate(*a, **k):
        called["n"] += 1

    monkeypatch.setattr(admin, "_do_generate", fake_do_generate)
    state = _FakeState({"custom_topic": "x"})
    msg = SimpleNamespace(from_user=SimpleNamespace(id=1), text="300")
    await admin.fb_custom_length(msg, bot=object(), state=state)
    assert called["n"] == 0
