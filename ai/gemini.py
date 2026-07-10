"""Обёртка над Google GenAI SDK: Vertex AI (основной) + AI Studio (резерв).

Основной клиент — Vertex через service account (ADC). При ошибке (лимит/блок)
переключаемся на резервный клиент AI Studio с ключом GEMINI_API_KEY_FALLBACK.
"""
import logging

import config  # noqa: F401  — выполняет load_dotenv() до создания клиента
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_client: genai.Client | None = None
_fallback: genai.Client | None = None


def get_client() -> genai.Client:
    """Ленивая инициализация основного клиента (Vertex из окружения)."""
    global _client
    if _client is None:
        _client = genai.Client()
        logger.info("GenAI client создан (Vertex=%s, project=%s, location=%s)",
                    config.GOOGLE_GENAI_USE_VERTEXAI,
                    config.GOOGLE_CLOUD_PROJECT,
                    config.GOOGLE_CLOUD_LOCATION)
    return _client


def get_fallback_client() -> genai.Client | None:
    """Резервный клиент AI Studio по ключу GEMINI_API_KEY_FALLBACK."""
    global _fallback
    if not config.GEMINI_API_KEY_FALLBACK:
        return None
    if _fallback is None:
        _fallback = genai.Client(api_key=config.GEMINI_API_KEY_FALLBACK)
        logger.info("GenAI fallback client создан (AI Studio)")
    return _fallback


def _clients() -> list[tuple[str, genai.Client]]:
    out: list[tuple[str, genai.Client]] = [("primary", get_client())]
    fb = get_fallback_client()
    if fb is not None:
        out.append(("fallback", fb))
    return out


def generate_text(prompt: str, *, temperature: float = 0.9,
                  max_output_tokens: int = 8192,
                  use_search: bool = False) -> str:
    """Генерация текста с автопереключением primary -> fallback.

    use_search=True подключает Google Search grounding — модель опирается
    на свежие материалы из интернета (актуальные новости/факты).
    """
    tools = (
        [types.Tool(google_search=types.GoogleSearch())]
        if use_search else None
    )
    last_err: Exception | None = None
    for name, client in _clients():
        try:
            resp = client.models.generate_content(
                model=config.GEMINI_TEXT_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    tools=tools,
                ),
            )
            if name == "fallback":
                logger.warning("generate_text: использован резервный ключ")
            return (resp.text or "").strip()
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.warning("generate_text через %s не удалось: %s", name, e)
    if last_err:
        raise last_err
    return ""


def generate_image(prompt: str) -> bytes | None:
    """Генерация картинки с автопереключением primary -> fallback."""
    last_err: Exception | None = None
    for name, client in _clients():
        try:
            resp = client.models.generate_content(
                model=config.GEMINI_IMAGE_MODEL,
                contents=prompt,
            )
            if not resp.candidates:
                logger.warning("generate_image через %s: пустой candidates", name)
                continue
            for part in resp.candidates[0].content.parts:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    if name == "fallback":
                        logger.warning("generate_image: использован резервный ключ")
                    return inline.data
            logger.warning("Картинка не сгенерирована (%s): %.80s", name, prompt)
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.warning("generate_image через %s не удалось: %s", name, e)
    if last_err:
        logger.error("generate_image: все клиенты упали: %s", last_err)
    return None
