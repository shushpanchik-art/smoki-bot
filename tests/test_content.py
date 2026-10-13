"""Тесты чистой логики контента: _split, _clean_html, censor."""
import pytest

from services import content
from services.publisher import _split


# ---------- _split (разбивка по лимиту Telegram) ----------
def test_split_short_returns_one_part():
    assert _split("короткий текст", 100) == ["короткий текст"]


def test_split_respects_limit():
    text = "\n\n".join(["абзац " * 10 for _ in range(20)])
    parts = _split(text, 200)
    assert all(len(p) <= 200 for p in parts)
    assert len(parts) > 1


def test_split_hard_cuts_oversized_paragraph():
    para = "x" * 500
    parts = _split(para, 100)
    assert all(len(p) <= 100 for p in parts)
    # весь текст сохранён
    assert "".join(parts) == para


def test_split_never_empty():
    assert _split("", 100) == [""]


# ---------- _clean_html ----------
def test_clean_html_strips_code_fence():
    assert content._clean_html("```html\n<b>hi</b>\n```") == "<b>hi</b>"


def test_clean_html_removes_headers():
    out = content._clean_html("<h1>Заголовок</h1>текст")
    assert "<h1>" not in out and "Заголовок" in out


def test_clean_html_li_to_bullet():
    out = content._clean_html("<ul><li>раз</li><li>два</li></ul>")
    assert "•" in out and "<li>" not in out and "<ul>" not in out


def test_clean_html_collapses_blank_lines():
    out = content._clean_html("a\n\n\n\n\nb")
    assert "\n\n\n" not in out


def test_clean_html_keeps_allowed_tags():
    out = content._clean_html("<b>жирный</b> <i>курсив</i>")
    assert "<b>" in out and "<i>" in out


# ---------- censor (мок _text) ----------
async def test_censor_ok_verdict(monkeypatch):
    async def fake_text(prompt, **kw):
        return "OK"
    monkeypatch.setattr(content, "_text", fake_text)
    ok, res = await content.censor("исходный текст")
    assert ok is True
    assert res == "исходный текст"


async def test_censor_short_reply_fails(monkeypatch):
    async def fake_text(prompt, **kw):
        return "нельзя"
    monkeypatch.setattr(content, "_text", fake_text)
    ok, res = await content.censor("текст")
    assert ok is False


async def test_censor_empty_reply_fails(monkeypatch):
    async def fake_text(prompt, **kw):
        return "   "
    monkeypatch.setattr(content, "_text", fake_text)
    ok, res = await content.censor("текст")
    assert ok is False
    assert res


async def test_censor_returns_edited_text(monkeypatch):
    edited = ("исправленный текст " * 20).strip()  # > 200 символов
    async def fake_text(prompt, **kw):
        return edited
    monkeypatch.setattr(content, "_text", fake_text)
    ok, res = await content.censor("оригинал")
    assert ok is True
    assert res == edited


def test_clean_html_markdown_bold_to_html():
    assert content._clean_html("**жирный**") == "<b>жирный</b>"
    assert content._clean_html("__тоже__") == "<b>тоже</b>"


def test_clean_html_markdown_italic_to_html():
    assert content._clean_html("*курсив*") == "<i>курсив</i>"
    assert content._clean_html("текст _вот_ тут") == "текст <i>вот</i> тут"


def test_clean_html_keeps_existing_html():
    assert content._clean_html("<b>ready</b>") == "<b>ready</b>"


def test_clean_html_does_not_break_urls_and_words():
    # подчёркивания в URL и snake_case, умножение — не курсив
    assert content._clean_html("https://ex.com/a_b_c") == "https://ex.com/a_b_c"
    assert content._clean_html("snake_case_var") == "snake_case_var"
    assert content._clean_html("5 * 3 = 15") == "5 * 3 = 15"


# ---------- Hybrid search (Serper API) ----------
pytestmark = pytest.mark.asyncio


async def test_detect_news_topic():
    """Определение новостных тем по ключевым словам."""
    assert await content._detect_news_topic("Новые правила продажи вейпов") is True
    assert await content._detect_news_topic("Законы о кальянах изменились") is True
    assert await content._detect_news_topic("История табакокурения") is False
    assert await content._detect_news_topic("Обзор новых под-систем") is False


async def test_enrich_with_news_no_api_key(monkeypatch):
    """Без SERPER_API_KEY возвращает None (fallback)."""
    import config

    monkeypatch.setattr(config, "SERPER_API_KEY", "")

    result = await content._enrich_with_news("Новости о вейпах")
    assert result is None


async def test_enrich_with_news_not_news_topic(monkeypatch):
    """Не новостная тема → None без вызова API."""
    result = await content._enrich_with_news("История кальянов")
    assert result is None


async def test_enrich_with_news_success(monkeypatch):
    """Успешное обогащение новостного контекста."""
    from ai import search as ai_search

    async def fake_search(query, **kw):
        return [
            {"title": "Новость 1", "snippet": "Текст 1",
             "source": "Источник 1", "date": "2026-10-13", "link": "https://ex.com/1"}
        ]

    monkeypatch.setattr(ai_search, "search_news", fake_search)

    result = await content._enrich_with_news("Новые законы о вейпах")
    assert result is not None
    context, source = result
    assert source == "serper"
    assert "Новость 1" in context
