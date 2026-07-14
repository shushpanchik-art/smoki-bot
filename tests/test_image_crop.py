"""Тесты центрального кропа картинки под 4:5 (портрет)."""
import io

from PIL import Image

from ai.gemini import _crop_landscape


def _png(w: int, h: int, colour: tuple = (10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(buf, format="PNG")
    return buf.getvalue()


def _size(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


def test_square_becomes_portrait():
    out = _crop_landscape(_png(1024, 1024))
    w, h = _size(out)
    # ratio=4/5=0.8: target_h=1024/0.8=1280>1024 -> режем ширину
    assert w == 819  # round(1024 * 0.8)
    assert h == 1024
    assert h > w  # портрет
    assert abs(w / h - 0.8) < 0.01


def test_wide_becomes_portrait():
    # очень широкая (4:1) -> режем по ширине до 4:5
    out = _crop_landscape(_png(2000, 500))
    w, h = _size(out)
    assert h == 500
    assert w == 400  # round(500 * 0.8)
    assert abs(w / h - 0.8) < 0.01


def test_broken_bytes_returns_original():
    junk = b"not-an-image"
    assert _crop_landscape(junk) == junk


def test_custom_ratio():
    out = _crop_landscape(_png(1000, 1000), ratio=16 / 9)
    w, h = _size(out)
    assert w == 1000
    assert abs(w / h - 16 / 9) < 0.02


def test_trim_removes_white_bars():
    from ai.gemini import _trim_borders

    img = Image.new("RGB", (1024, 1024), (255, 255, 255))
    for y in range(200, 824):
        for x in range(1024):
            img.putpixel((x, y), (10, 120, 60))
    assert _trim_borders(img).size[1] < 1024


def test_trim_keeps_full_when_no_bars():
    from ai.gemini import _trim_borders

    img = Image.new("RGB", (600, 400), (30, 30, 30))
    for x in range(600):
        img.putpixel((x, 0), (200, 10, 10))
    assert _trim_borders(img).size == (600, 400)
