"""Анализ тональности статей через Gemini API.

U15 — Определение sentiment (positive/neutral/negative) для балансировки контента.
Помогает избежать серий негативных статей подряд.
"""
import logging

from ai.gemini import generate_text

logger = logging.getLogger("smoki.sentiment")


async def analyze_sentiment(text: str) -> dict[str, str | float]:
    """Анализировать тональность текста через Gemini.

    Args:
        text: Текст статьи для анализа

    Returns:
        {
            "label": "positive" | "neutral" | "negative",
            "score": float от -1.0 до +1.0
        }

    Example:
        result = await analyze_sentiment("Отличные новости! Новые вкусы...")
        # {"label": "positive", "score": 0.8}
    """
    if not text or len(text) < 10:
        return {"label": "neutral", "score": 0.0}

    # Берём первые 500 символов для анализа (достаточно для определения тона)
    sample = text[:500]

    prompt = f"""Определи тональность текста одним словом: positive, neutral или negative.

Текст:
{sample}

Ответ (только одно слово):"""

    try:
        label = await generate_text(prompt, use_search=False)
        label = label.strip().lower()

        # Валидация ответа
        if label not in ("positive", "neutral", "negative"):
            logger.warning("Неожиданный ответ sentiment: %s, defaulting to neutral", label)
            label = "neutral"

        # Маппинг в score
        score_map = {
            "positive": 0.7,
            "neutral": 0.0,
            "negative": -0.7
        }
        score = score_map[label]

        return {"label": label, "score": score}

    except Exception as e:
        logger.warning("Ошибка анализа sentiment: %s", e)
        return {"label": "neutral", "score": 0.0}


def sentiment_to_emoji(label: str) -> str:
    """Конвертировать label в эмодзи для отображения.

    Args:
        label: "positive", "neutral" или "negative"

    Returns:
        Эмодзи: ✅ / ⚪ / ❌
    """
    emoji_map = {
        "positive": "✅",
        "neutral": "⚪",
        "negative": "❌"
    }
    return emoji_map.get(label, "⚪")
