"""U4: одношаговый ввод темы+длины (fb_custom_topic).

Тема и желаемая длина указываются в одном сообщении; хендлер парсит
число слов через prompts.custom_words_rule и передаёт в _do_generate.
Не-админ игнорируется.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import config
from ai import prompts
from handlers import admin


class _FakeState:
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
async def test_topic_with_words_sets_hint(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 555)
    captured = {}

    async def fake_do_generate(message, bot, mode="", topic=None,
                               length_hint=None):
        captured["topic"] = topic
        captured["length_hint"] = length_hint

    monkeypatch.setattr(admin, "_do_generate", fake_do_generate)
    state = _FakeState()
    msg = SimpleNamespace(
        from_user=SimpleNamespace(id=555),
        text="табак, 350 слов",
        answer=AsyncMock(),
    )
    await admin.fb_custom_topic(msg, bot=object(), state=state)

    assert captured["topic"] == "табак, 350 слов"
    assert captured["length_hint"] == prompts.custom_words_rule(350, default=150)
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_topic_without_words_default(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 555)
    captured = {}

    async def fake_do_generate(message, bot, mode="", topic=None,
                               length_hint=None):
        captured["length_hint"] = length_hint

    monkeypatch.setattr(admin, "_do_generate", fake_do_generate)
    state = _FakeState()
    msg = SimpleNamespace(
        from_user=SimpleNamespace(id=555),
        text="вейпы и здоровье",
        answer=AsyncMock(),
    )
    await admin.fb_custom_topic(msg, bot=object(), state=state)

    assert captured["length_hint"] == prompts.custom_words_rule(None, default=150)


@pytest.mark.asyncio
async def test_dash_means_no_topic(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 555)
    captured = {}

    async def fake_do_generate(message, bot, mode="", topic=None,
                               length_hint=None):
        captured["topic"] = topic

    monkeypatch.setattr(admin, "_do_generate", fake_do_generate)
    state = _FakeState()
    msg = SimpleNamespace(
        from_user=SimpleNamespace(id=555), text="-", answer=AsyncMock()
    )
    await admin.fb_custom_topic(msg, bot=object(), state=state)
    assert captured["topic"] is None


@pytest.mark.asyncio
async def test_non_admin_ignored(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 555)
    called = {"n": 0}

    async def fake_do_generate(*a, **k):
        called["n"] += 1

    monkeypatch.setattr(admin, "_do_generate", fake_do_generate)
    state = _FakeState()
    msg = SimpleNamespace(
        from_user=SimpleNamespace(id=1), text="табак 300 слов",
        answer=AsyncMock(),
    )
    await admin.fb_custom_topic(msg, bot=object(), state=state)
    assert called["n"] == 0
