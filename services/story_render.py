"""Наложение русского текста на картинку сторис через Pillow.

Image-модель (gemini-2.5-flash-image) не умеет рисовать читаемую кириллицу,
поэтому генерим ЧИСТЫЙ фон без текста, а подпись накладываем сами: крупный
DejaVuSans-Bold, перенос по словам, полупрозрачная тёмная подложка снизу.
"""
from __future__ import annotations

import io
import logging
import textwrap

logger = logging.getLogger(__name__)

# Системный шрифт с кириллицей (Debian: fonts-dejavu-core).
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Итоговый холст сторис 9:16.
CANVAS_W = 1080
CANVAS_H = 1920

_FONT_SIZE = 64
_LINE_SPACING = 14
_SIDE_MARGIN = 80
_BOTTOM_MARGIN = 160
_PAD = 40           # внутренний отступ подложки
_MAX_CHARS = 26     # ширина строки для переноса (эмпирически под FONT_SIZE)
_MAX_LINES = 6      # больше строк не рисуем (обрезаем с многоточием)


def render_story_caption(image_bytes: bytes, caption: str) -> bytes:
    """Кладёт caption на нижнюю часть картинки. Ошибки не критичны — вернём исходник.

    Возвращает PNG-байты холста 1080x1920 с наложенным текстом.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        src = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        # Приводим к 9:16, заполняя кадр (cover): масштаб + центральный кроп.
        canvas = _fit_cover(src, CANVAS_W, CANVAS_H)

        text = " ".join((caption or "").split())
        if not text:
            return _to_png(canvas)

        try:
            font = ImageFont.truetype(FONT_PATH, _FONT_SIZE)
        except OSError:
            logger.warning("Шрифт %s не найден, текст не наложен", FONT_PATH)
            return _to_png(canvas)

        lines = _wrap(text)
        draw = ImageDraw.Draw(canvas, "RGBA")

        # Высота блока текста.
        line_h = _line_height(font)
        block_h = len(lines) * line_h + (len(lines) - 1) * _LINE_SPACING
        box_top = CANVAS_H - _BOTTOM_MARGIN - block_h - 2 * _PAD
        box_top = max(box_top, 0)

        # Полупрозрачная подложка.
        draw.rectangle(
            [(0, box_top), (CANVAS_W, CANVAS_H)],
            fill=(0, 0, 0, 150),
        )

        y = box_top + _PAD
        for line in lines:
            w = _text_width(draw, line, font)
            x = (CANVAS_W - w) // 2
            # Тень для контраста.
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 200))
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
            y += line_h + _LINE_SPACING

        return _to_png(canvas)
    except Exception as e:  # noqa: BLE001
        logger.warning("render_story_caption не удался, отдаю оригинал: %s", e)
        return image_bytes


def _wrap(text: str) -> list[str]:
    lines = textwrap.wrap(text, width=_MAX_CHARS)
    if len(lines) > _MAX_LINES:
        lines = lines[:_MAX_LINES]
        lines[-1] = lines[-1].rstrip(".,;: ") + "…"
    return lines


def _line_height(font) -> int:
    ascent, descent = font.getmetrics()
    return ascent + descent


def _text_width(draw, line: str, font) -> int:
    left, _, right, _ = draw.textbbox((0, 0), line, font=font)
    return right - left


def _fit_cover(src, target_w: int, target_h: int):
    """Масштабирует src до полного покрытия target и центрально кропает."""
    from PIL import Image

    sw, sh = src.size
    if sw <= 0 or sh <= 0:
        return Image.new("RGB", (target_w, target_h), (20, 20, 20))
    scale = max(target_w / sw, target_h / sh)
    new_w = max(1, int(round(sw * scale)))
    new_h = max(1, int(round(sh * scale)))
    resized = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _to_png(img) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
