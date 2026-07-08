"""Обёртка над Google GenAI SDK через Vertex AI.

Аутентификация — service account (ADC) на сервере, без API-ключа.
Переменные окружения (GOOGLE_GENAI_USE_VERTEXAI, GOOGLE_CLOUD_PROJECT,
GOOGLE_CLOUD_LOCATION) подтягиваются из .env через config.load_dotenv().
"""
import logging

import config  # noqa: F401  — выполняет load_dotenv() до создания клиента
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Ленивая инициализация клиента (Vertex подхватится из окружения)."""
    global _client
    if _client is None:
        _client = genai.Client()
        logger.info("GenAI client создан (Vertex=%s, project=%s, location=%s)",
                    config.GOOGLE_GENAI_USE_VERTEXAI,
                    config.GOOGLE_CLOUD_PROJECT,
                    config.GOOGLE_CLOUD_LOCATION)
    return _client


def generate_text(prompt: str, *, temperature: float = 0.9,
                  max_output_tokens: int = 8192) -> str:
    """Генерация текста. Возвращает строку ответа."""
    client = get_client()
    resp = client.models.generate_content(
        model=config.GEMINI_TEXT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ),
    )
    return (resp.text or "").strip()


def generate_image(prompt: str) -> bytes | None:
    """Генерация картинки. Возвращает байты изображения или None."""
    client = get_client()
    resp = client.models.generate_content(
        model=config.GEMINI_IMAGE_MODEL,
        contents=prompt,
    )
    if not resp.candidates:
        logger.warning("generate_image: пустой candidates (возможно safety-блок)")
        return None
    for part in resp.candidates[0].content.parts:
        inline = getattr(part, "inline_data", None)
        if inline and inline.data:
            return inline.data
    logger.warning("Картинка не сгенерирована для промпта: %.80s", prompt)
    return None
