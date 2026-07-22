"""Обёртка над Google GenAI SDK: Vertex AI (основной) + AI Studio (резерв).

Основной клиент — Vertex через service account (ADC). При ошибке (лимит/блок)
переключаемся на резервный клиент AI Studio с ключом GEMINI_API_KEY_FALLBACK.
"""
import logging
import time
from typing import TYPE_CHECKING

import config  # noqa: F401  — выполняет load_dotenv() до создания клиента
from google import genai
from google.genai import errors, types

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

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


_MAX_ATTEMPTS = 3
_BASE_DELAY = 1.0


def _is_transient(err: Exception) -> bool:
    """5xx или 429 — стоит повторить; прочее — нет."""
    if isinstance(err, errors.ServerError):
        return True
    if isinstance(err, errors.ClientError):
        return getattr(err, "code", None) == 429
    return False


def _call_with_retry(fn, label):
    """Повторяет вызов при транзиентных ошибках с экспопаузой."""
    last: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if not _is_transient(e) or attempt == _MAX_ATTEMPTS:
                raise
            delay = _BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "%s: транзиентная ошибка (попытка %d/%d), пауза %.1fs: %s",
                label, attempt, _MAX_ATTEMPTS, delay, e,
            )
            time.sleep(delay)
    if last:
        raise last
    raise RuntimeError("unreachable")


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
    tools: types.ToolListUnion | None = (
        [types.Tool(google_search=types.GoogleSearch())]
        if use_search else None
    )
    last_err: Exception | None = None
    for name, client in _clients():
        try:
            resp = _call_with_retry(
                lambda c=client: c.models.generate_content(
                    model=config.GEMINI_TEXT_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                        tools=tools,
                    ),
                ),
                f"generate_text[{name}]",
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


def _trim_borders(img: "PILImage", tol: int = 12) -> "PILImage":
    """Срезает однотонные (белые/чёрные) поля по краям картинки.

    Берём цвет угла как фон, строим разницу, ищем bbox реального контента.
    Если фон не найден или bbox пустой — возвращаем исходник без изменений.
    """
    from PIL import Image, ImageChops

    rgb = img.convert("RGB")
    w, h = rgb.size
    # предполагаемый цвет фона = левый верхний пиксель
    bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    diff = ImageChops.difference(rgb, bg)
    # усиливаем разницу, чтобы отсечь шум сжатия по порогу tol
    diff = diff.point(lambda x: 255 if x > tol else 0)
    bbox = diff.getbbox()
    if not bbox:
        return img
    left, top, right, bottom = bbox
    # игнорируем микрообрезку (<2% с каждой стороны) — не трогаем контент зря
    trimmed = (left + (w - right)) + (top + (h - bottom))
    if trimmed < (w + h) * 0.02:
        return img
    return img.crop(bbox)


def _crop_landscape(data: bytes, ratio: float = 4 / 5) -> bytes:
    """Центральный кроп PNG под портретный формат (по умолчанию 4:5).

    flash-image всегда отдаёт квадрат 1024x1024; SDK не умеет aspect_ratio,
    поэтому режем сами. Сначала срезаем однотонные поля (white/black bars),
    затем приводим к нужному соотношению. Ошибки не критичны — отдаём исходник.
    """
    try:
        import io

        from PIL import Image

        opened = Image.open(io.BytesIO(data))
        src = _trim_borders(opened)
        w, h = src.size
        if w <= 0 or h <= 0:
            return data
        target = w / ratio  # желаемая высота при полной ширине
        if target <= h:
            new_h = int(round(target))
            top = (h - new_h) // 2
            cropped = src.crop((0, top, w, top + new_h))
        else:
            new_w = int(round(h * ratio))
            left = (w - new_w) // 2
            cropped = src.crop((left, 0, left + new_w, h))
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:  # noqa: BLE001
        logger.warning("_crop_landscape не удался, отдаю оригинал: %s", e)
        return data


def generate_image(prompt: str) -> bytes | None:
    """Генерация картинки с автопереключением primary -> fallback."""
    last_err: Exception | None = None
    for name, client in _clients():
        try:
            resp = _call_with_retry(
                lambda c=client: c.models.generate_content(
                    model=config.GEMINI_IMAGE_MODEL,
                    contents=prompt,
                ),
                f"generate_image[{name}]",
            )
            if not resp.candidates:
                logger.warning("generate_image через %s: пустой candidates", name)
                continue
            for part in resp.candidates[0].content.parts:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    if name == "fallback":
                        logger.warning("generate_image: использован резервный ключ")
                    return _crop_landscape(inline.data)
            logger.warning("Картинка не сгенерирована (%s): %.80s", name, prompt)
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.warning("generate_image через %s не удалось: %s", name, e)
    if last_err:
        logger.error("generate_image: все клиенты упали: %s", last_err)
    return None
