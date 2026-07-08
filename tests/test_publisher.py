"""Тесты разбивки текста publisher._split (Telegram-лимиты)."""
from services.publisher import _split, TG_TEXT_LIMIT


def test_split_short_returns_one_part():
    assert _split("Короткий текст", TG_TEXT_LIMIT) == ["Короткий текст"]


def test_split_empty_does_not_crash():
    res = _split("", TG_TEXT_LIMIT)
    assert isinstance(res, list) and len(res) >= 1


def test_split_never_exceeds_limit():
    text = ("абзац " * 200 + "\n\n") * 20
    for part in _split(text, TG_TEXT_LIMIT):
        assert len(part) <= TG_TEXT_LIMIT


def test_split_hard_cuts_oversized_paragraph():
    text = "x" * (TG_TEXT_LIMIT * 3 + 100)
    parts = _split(text, TG_TEXT_LIMIT)
    assert len(parts) >= 3
    for part in parts:
        assert len(part) <= TG_TEXT_LIMIT
    assert "".join(parts) == text


def test_split_respects_paragraph_boundaries():
    p1 = "a" * 100
    p2 = "b" * 100
    parts = _split(f"{p1}\n\n{p2}", TG_TEXT_LIMIT)
    assert len(parts) == 1
    assert p1 in parts[0] and p2 in parts[0]
