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


# --- R3: retry на транзиентных ошибках -------------------------------------

class _FakeServer(gemini.errors.ServerError):
    def __init__(self):  # noqa: D401 — не зовём тяжёлый APIError.__init__
        self.code = 500


class _FakeClient429(gemini.errors.ClientError):
    def __init__(self):
        self.code = 429


class _FakeClient400(gemini.errors.ClientError):
    def __init__(self):
        self.code = 400


def test_is_transient_classification():
    assert gemini._is_transient(_FakeServer()) is True
    assert gemini._is_transient(_FakeClient429()) is True
    assert gemini._is_transient(_FakeClient400()) is False
    assert gemini._is_transient(ValueError("boom")) is False


def test_retry_success_after_transient(monkeypatch):
    sleeps = []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: sleeps.append(s))
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _FakeServer()
        return "ok"

    assert gemini._call_with_retry(fn, "lbl") == "ok"
    assert calls["n"] == 3
    assert len(sleeps) == 2  # две паузы перед 2-й и 3-й попыткой


def test_retry_exhausts_and_raises(monkeypatch):
    sleeps = []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: sleeps.append(s))

    def fn():
        raise _FakeServer()

    with pytest.raises(gemini.errors.ServerError):
        gemini._call_with_retry(fn, "lbl")
    assert len(sleeps) == gemini._MAX_ATTEMPTS - 1


def test_no_retry_on_permanent(monkeypatch):
    sleeps = []
    monkeypatch.setattr(gemini.time, "sleep", lambda s: sleeps.append(s))
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise _FakeClient400()

    with pytest.raises(gemini.errors.ClientError):
        gemini._call_with_retry(fn, "lbl")
    assert calls["n"] == 1
    assert sleeps == []
