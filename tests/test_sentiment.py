"""Sentiment regression coverage without external API calls."""
import threading
from unittest.mock import Mock

import pytest

from ai import sentiment


@pytest.mark.asyncio
@pytest.mark.parametrize("response,label,score", [
    (" Positive \n", "positive", 0.7),
    ("negative", "negative", -0.7),
    ("neutral", "neutral", 0.0),
    ("unexpected", "neutral", 0.0),
])
async def test_sync_generator_runs_outside_event_loop(monkeypatch, response, label, score):
    loop_thread = threading.get_ident()
    calls = []

    def generate(prompt, *, use_search):
        calls.append((threading.get_ident(), prompt, use_search))
        return response

    monkeypatch.setattr(sentiment, "generate_text", generate)
    text = "sample article " * 50
    assert await sentiment.analyze_sentiment(text) == {"label": label, "score": score}
    assert len(calls) == 1
    worker, prompt, use_search = calls[0]
    assert worker != loop_thread
    assert text[:500] in prompt
    assert text[:501] not in prompt
    assert use_search is False


@pytest.mark.asyncio
async def test_generator_error_returns_neutral(monkeypatch):
    generate = Mock(side_effect=RuntimeError("synthetic API failure"))
    monkeypatch.setattr(sentiment, "generate_text", generate)
    assert await sentiment.analyze_sentiment("article long enough") == {
        "label": "neutral", "score": 0.0,
    }
    generate.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["", "short"])
async def test_short_input_skips_generation(monkeypatch, text):
    generate = Mock()
    monkeypatch.setattr(sentiment, "generate_text", generate)
    assert await sentiment.analyze_sentiment(text) == {"label": "neutral", "score": 0.0}
    generate.assert_not_called()
