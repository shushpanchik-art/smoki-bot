"""Устойчивость обёртки gemini на моках (без реального API)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ai import gemini


@pytest.fixture(autouse=True)
def reset_client(monkeypatch):
    """Сбрасываем синглтон перед каждым тестом."""
    monkeypatch.setattr(gemini, "_client", None)


def _fake_client(text_resp=None, image_parts=None):
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(
        text=text_resp,
        candidates=image_parts,
    )
    return client


def test_generate_text_ok(monkeypatch):
    monkeypatch.setattr(gemini, "get_client", lambda: _fake_client(text_resp="  Привет  "))
    assert gemini.generate_text("prompt") == "Привет"


def test_generate_text_none_returns_empty(monkeypatch):
    """resp.text=None не должен ронять — пустая строка."""
    monkeypatch.setattr(gemini, "get_client", lambda: _fake_client(text_resp=None))
    assert gemini.generate_text("prompt") == ""


def test_generate_image_no_data_returns_none(monkeypatch):
    """Нет inline-data — функция возвращает None, не падает."""
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(candidates=[])
    monkeypatch.setattr(gemini, "get_client", lambda: client)
    assert gemini.generate_image("prompt") is None


def test_get_client_is_singleton(monkeypatch):
    created = []

    class FakeGenai:
        def Client(self):
            c = MagicMock()
            created.append(c)
            return c

    monkeypatch.setattr(gemini, "genai", FakeGenai())
    c1 = gemini.get_client()
    c2 = gemini.get_client()
    assert c1 is c2
    assert len(created) == 1
