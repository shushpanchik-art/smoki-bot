"""Проверка Pillow-наложения текста на сторис."""
import io

from PIL import Image

from services import story_render


def _fake_png(w: int = 1024, h: int = 1024) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 60, 90)).save(buf, format="PNG")
    return buf.getvalue()


def test_render_returns_916_png():
    out = story_render.render_story_caption(_fake_png(), "Тестовая подпись сторис")
    img = Image.open(io.BytesIO(out))
    assert img.size == (story_render.CANVAS_W, story_render.CANVAS_H)
    assert img.format == "PNG"


def test_render_empty_caption_ok():
    out = story_render.render_story_caption(_fake_png(), "")
    img = Image.open(io.BytesIO(out))
    assert img.size == (story_render.CANVAS_W, story_render.CANVAS_H)


def test_render_long_caption_no_crash():
    long_text = "Очень длинная подпись " * 40
    out = story_render.render_story_caption(_fake_png(), long_text)
    assert Image.open(io.BytesIO(out)).size == (
        story_render.CANVAS_W,
        story_render.CANVAS_H,
    )


def test_render_bad_bytes_returns_input():
    junk = b"not an image"
    assert story_render.render_story_caption(junk, "текст") == junk
