"""Проверка шаблонов промптов: не пустые, содержат подстановки."""

from ai import prompts


def test_article_prompt_contains_topic():
    out = prompts.article_prompt("Вейпы")
    assert "Вейпы" in out
    assert len(out) > 50


def test_article_prompt_with_used_topics():
    out = prompts.article_prompt("Тема", used_topics=["старая1", "старая2"])
    assert "старая1" in out or "старая2" in out


def test_article_prompt_with_extra_rules():
    out = prompts.article_prompt("Тема", extra_rules="без мата")
    assert "без мата" in out


def test_topic_prompt_not_empty():
    assert len(prompts.topic_prompt()) > 30


def test_image_prompt_contains_topic():
    out = prompts.image_prompt("hookah")
    assert "hookah" in out


def test_censor_prompt_contains_text():
    out = prompts.censor_prompt("проверяемый текст")
    assert "проверяемый текст" in out


def test_classify_comment_prompt_contains_comment():
    out = prompts.classify_comment_prompt("это спам")
    assert "это спам" in out


def test_reply_comment_prompt_contains_comment():
    out = prompts.reply_comment_prompt("вопрос", "question")
    assert "вопрос" in out


def test_niche_constants_not_empty():
    assert prompts.NICHE.strip()
    assert prompts.ARTICLE_SYSTEM.strip()
    assert prompts.CENSOR_RULES.strip()
