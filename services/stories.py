"""U6.2b: генерация сторис-слотов для @SMOKTOLK и реюз во flood-группе.

Планировщик раз в день раскладывает N случайных слотов (по лимитам config),
на каждый слот выбирается тема по весам, генерируется текст+вертикальная
картинка 9:16 и пишется story_job(status='pending') на модерацию.
"""
import asyncio
import logging
import random
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import config
from ai import gemini, prompts
from db import database as db
from services import story_render

logger = logging.getLogger("smoki.stories")

IMAGE_DIR = Path(config.IMAGE_DIR)

# темы 1-5 с весами из config; 1..4 используют поиск, 5 (пожелание) — нет
_THEME_WEIGHTS = {
    1: config.STORY_WEIGHT_JOKE,
    2: config.STORY_WEIGHT_NEWS,
    3: config.STORY_WEIGHT_NEW_PRODUCTS,
    4: config.STORY_WEIGHT_FACT,
    5: config.STORY_WEIGHT_WISH,
}
_SEARCH_THEMES = {2, 3, 4}


def pick_theme() -> int:
    """Случайная тема 1..5 по весам config (детерминирована только суммой)."""
    themes = list(_THEME_WEIGHTS.keys())
    weights = [max(0, _THEME_WEIGHTS[t]) for t in themes]
    if sum(weights) <= 0:
        return random.choice(themes)
    return random.choices(themes, weights=weights, k=1)[0]


def _daily_count(min_v: int, max_v: int) -> int:
    lo, hi = min(min_v, max_v), max(min_v, max_v)
    return random.randint(lo, hi)


def _slot_times(count: int, start_h: int = 10, end_h: int = 22) -> list[str]:
    """count равномерно-случайных ISO-времён на сегодня в окне [start_h,end_h)."""
    now = datetime.now()
    span_min = max(1, (end_h - start_h) * 60)
    step = span_min // max(1, count)
    out: list[str] = []
    for i in range(count):
        base = start_h * 60 + i * step
        jitter = random.randint(0, max(0, step - 1))
        total = min(base + jitter, end_h * 60 - 1)
        dt = now.replace(hour=0, minute=0, second=0, microsecond=0) \
            + timedelta(minutes=total)
        out.append(dt.replace(microsecond=0).isoformat())
    return out


async def _text(prompt: str, **kw) -> str:
    out = await asyncio.to_thread(gemini.generate_text, prompt, **kw)
    try:
        await db.log_ai("story_text", config.GEMINI_TEXT_MODEL,
                        input_tokens=len(prompt) // 4,
                        output_tokens=len(out) // 4)
    except Exception:
        logger.exception("log_ai story_text")
    return (out or "").strip()


async def _image(prompt: str) -> bytes | None:
    data = await asyncio.to_thread(gemini.generate_image, prompt)
    try:
        await db.log_ai("story_image", config.GEMINI_IMAGE_MODEL,
                        input_tokens=len(prompt) // 4)
    except Exception:
        logger.exception("log_ai story_image")
    return data


async def generate_channel_slot(theme: int | None = None,
                                publish_at: str | None = None) -> int | None:
    """Один слот канала: текст → сцена → вертикальная картинка → story_job.

    Возвращает job_id (status='pending') или None при провале картинки.
    """
    if theme is None:
        theme = pick_theme()
    use_search = theme in _SEARCH_THEMES

    snippet = ""
    if use_search:
        try:
            snippet = await _text(prompts.story_text_prompt(theme),
                                  use_search=True)
        except Exception:
            logger.exception("story поиск не удался, тема %s", theme)

    caption = await _text(prompts.story_text_prompt(theme, snippet))
    if not caption:
        caption = snippet[:200]

    scene = f"atmospheric background for topic: {prompts.STORY_THEMES.get(theme, '')}"
    img_prompt = prompts.story_image_prompt(scene)  # текст накладываем Pillow
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    image_path: str | None = None
    try:
        data = await _image(img_prompt)
        if data:
            data = await asyncio.to_thread(
                story_render.render_story_caption, data, caption or "",
            )
            fname = f"story_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
            fpath = IMAGE_DIR / fname
            fpath.write_bytes(data)
            image_path = str(fpath)
    except Exception:
        logger.exception("story картинка не сгенерирована, тема %s", theme)

    if not image_path:
        logger.warning("story слот без картинки пропущен (тема %s)", theme)
        return None

    job_id = await db.add_story_job(
        target="channel",
        theme=theme,
        prompt_en=img_prompt,
        image_path=image_path,
        caption=caption,
        publish_at=publish_at,
    )
    logger.info("Story-слот #%s создан (тема %s, publish_at=%s)",
                job_id, theme, publish_at)
    return job_id


async def generate_flood_slot(publish_at: str | None = None) -> int | None:
    """Реюз опубликованной картинки во flood-группе с новой подписью-фактом."""
    imgs = await db.get_published_story_images(limit=200)
    if not imgs:
        logger.info("flood: нет опубликованных картинок для реюза")
        return None
    src = random.choice(imgs)
    theme = src.get("theme") or pick_theme()

    snippet = ""
    try:
        snippet = await _text(prompts.story_flood_caption_prompt(theme),
                              use_search=True)
    except Exception:
        logger.exception("flood поиск не удался")
    caption = await _text(prompts.story_flood_caption_prompt(theme, snippet))
    if not caption:
        caption = snippet[:200]

    job_id = await db.add_story_job(
        target="flood",
        theme=theme,
        prompt_en=src.get("prompt_en"),
        image_path=src.get("image_path"),
        caption=caption,
        publish_at=publish_at,
    )
    logger.info("Flood-слот #%s создан (реюз img #%s)", job_id, src.get("id"))
    return job_id


async def plan_daily_channel() -> list[int]:
    """Разложить дневные слоты канала. Возвращает список созданных job_id."""
    count = _daily_count(config.STORY_CHANNEL_MIN_PER_DAY,
                         config.STORY_CHANNEL_MAX_PER_DAY)
    times = _slot_times(count)
    created: list[int] = []
    for t in times:
        jid = await generate_channel_slot(publish_at=t)
        if jid:
            created.append(jid)
    logger.info("plan_daily_channel: %d/%d слотов создано",
                len(created), count)
    return created


async def plan_daily_flood() -> list[int]:
    """Разложить дневные слоты flood-группы (реюз картинок)."""
    count = _daily_count(config.STORY_FLOOD_MIN_PER_DAY,
                         config.STORY_FLOOD_MAX_PER_DAY)
    times = _slot_times(count)
    created: list[int] = []
    for t in times:
        jid = await generate_flood_slot(publish_at=t)
        if jid:
            created.append(jid)
    logger.info("plan_daily_flood: %d/%d слотов создано", len(created), count)
    return created
