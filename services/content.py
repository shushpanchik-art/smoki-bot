"""Генерация контента: тема → статья → автоцензура → картинка."""
import asyncio
import datetime
import random
import logging
import re
import time
import uuid
from pathlib import Path

import config
from ai import gemini, prompts
from db import database as db

logger = logging.getLogger(__name__)

MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"
MEDIA_DIR.mkdir(exist_ok=True)


async def _text(prompt: str, **kw) -> str:
    """Async-обёртка над синхронным gemini.generate_text + лог."""
    t0 = time.time()
    out = await asyncio.to_thread(gemini.generate_text, prompt, **kw)
    try:
        await db.log_ai("text", config.GEMINI_TEXT_MODEL,
                        input_tokens=len(prompt) // 4,
                        output_tokens=len(out) // 4)
    except Exception:
        logger.exception("log_ai text")
    logger.info("generate_text %.1fs -> %d символов", time.time() - t0, len(out))
    return out


async def _image(prompt: str) -> bytes | None:
    t0 = time.time()
    data = await asyncio.to_thread(gemini.generate_image, prompt)
    try:
        await db.log_ai("image", config.GEMINI_IMAGE_MODEL,
                        input_tokens=len(prompt) // 4)
    except Exception:
        logger.exception("log_ai image")
    logger.info("generate_image %.1fs -> %s байт",
                time.time() - t0, len(data) if data else 0)
    return data


async def generate_topic() -> str:
    """Свежая тема строго в нише. Повтор при вылете за рамки."""
    used = await db.get_used_topics()
    keywords = (
        "вейп", "кальян", "табак", "сигарет", "испарит", "жидкост",
        "никотин", "под", "койл", "уголь", "чаш", "колб", "шланг",
        "курен", "дым", "смес", "ароматизат", "бренд", "устройств",
    )
    fallback = "Культура курения: интересные факты"
    last = fallback
    for _ in range(3):
        raw = await _text(prompts.topic_prompt(used), temperature=0.9,
                          max_output_tokens=512)
        topic = raw.strip().strip('«»"\'').split("\n")[0].strip()
        if not topic:
            continue
        last = topic
        if any(k in topic.lower() for k in keywords):
            return topic
        logger.warning("Тема вне ниши, повтор: %s", topic)
    return last or fallback


async def censor(text: str) -> tuple[bool, str]:
    """Автоцензура. Возвращает (ok, причина|очищенный_текст).

    Бренды МОЖНО. Нельзя: призывы к покупке/употреблению никотина, медсоветы.
    """
    verdict = await _text(prompts.censor_prompt(text), temperature=0.2,
                          max_output_tokens=8192)
    v = verdict.strip()
    # Ожидаем от модели: либо "OK", либо исправленный текст.
    if v.upper().startswith("OK"):
        return True, text
    # Если модель вернула отказ/пусто — считаем непройденным.
    if not v or len(v) < 200:
        return False, v or "Пустой ответ цензора"
    # Иначе модель вернула отредактированный текст — используем его.
    return True, v


def _clean_html(text: str) -> str:
    """Убрать запрещённые для Telegram теги, конвертировать Markdown в HTML."""
    # срезать возможные ```html ... ```
    text = re.sub(r"^```(?:html)?\s*|\s*```$", "", text.strip())
    # заменить неподдерживаемые теги на переносы/жирный
    text = re.sub(r"</?(h[1-6])>", "\n", text, flags=re.I)
    text = re.sub(r"<li>", "• ", text, flags=re.I)
    text = re.sub(r"</?(ul|ol|p|div|br)\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</li>", "\n", text, flags=re.I)
    # Markdown -> HTML (модель иногда игнорит запрет и сыплет **/*/_)
    # порядок важен: сначала двойные ** и __, потом одинарные * и _
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.S)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text, flags=re.S)
    # одинарные * / _ -> курсив, только парные вокруг непустого текста
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])",
                  r"<i>\1</i>", text, flags=re.S)
    text = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])",
                  r"<i>\1</i>", text, flags=re.S)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def _accumulated_rules(extra: str | None = None) -> str | None:
    """Склеить накопленный опыт (лайки/цензура) с разовым фидбэком."""
    parts: list[str] = []
    liked = await db.get_setting("liked_feedback")
    if liked:
        parts.append("Что нравится админу (следуй этому стилю):\n" + liked)
    censor = await db.get_setting("censor_extra")
    if censor:
        parts.append("Чего избегать (замечания админа):\n" + censor)
    if extra:
        parts.append("Разовые правки к этой статье:\n" + extra)
    return "\n\n".join(parts) if parts else None



async def _default_length_hint() -> str:
    """Выбор формата по текущему времени: утро→факты, иначе→лонг-рид.

    Источник длины ВСЕГДА бот, ИИ длину не выбирает.
    """
    hour = datetime.datetime.now().hour
    if config.MORNING_START <= hour < config.MORNING_END:
        n_max = int(await db.get_setting(
            "morning_facts", str(config.MORNING_LEN_DEFAULT))
            or config.MORNING_LEN_DEFAULT)
        n = random.randint(1, max(1, n_max))
        return prompts.facts_rules(n)
    w = int(await db.get_setting(
        "evening_words", str(config.EVENING_WORDS_DEFAULT))
        or config.EVENING_WORDS_DEFAULT)
    return prompts.words_rule(w)


async def generate_article(topic: str | None = None,
                           extra_rules: str | None = None,
                           length_hint: str | None = None,
                           make_image: bool = True) -> dict:
    """Полный цикл: тема → статья → цензура → картинка → запись в БД.

    Возвращает {article_id, topic, topic_id, body, image_path, ok, reason}.
    """
    if not topic:
        topic = await generate_topic()
    logger.info("Генерация статьи по теме: %s", topic)
    if length_hint is None:
        length_hint = await _default_length_hint()

    used = await db.get_used_topics()
    rules = await _accumulated_rules(extra_rules)
    daytime = prompts.daytime_label(datetime.datetime.now().hour)
    body_raw = await _text(
        prompts.article_prompt(
            topic, used, extra_rules=rules, length_hint=length_hint,
            daytime=daytime),
        use_search=True)
    body = _clean_html(body_raw)

    ok, result = await censor(body)
    if not ok:
        logger.warning("Цензура не пройдена: %.120s", result)
        return {"ok": False, "reason": result, "topic": topic}
    body = result

    image_path = None
    img_prompt = prompts.image_prompt(topic)  # фолбэк
    try:
        scene = (await _text(prompts.image_scene_prompt(body),
                              temperature=0.7)).strip()
        if scene:
            img_prompt = prompts.image_prompt_from_scene(scene, topic)
    except Exception:
        logger.exception("Не удалось извлечь сцену из текста, фолбэк на topic")
    if make_image:
        try:
            data = await _image(img_prompt)
            if data:
                fname = f"art_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
                fpath = MEDIA_DIR / fname
                fpath.write_bytes(data)
                image_path = str(fpath)
        except Exception:
            logger.exception("Ошибка генерации картинки")

    topic_id = await db.add_topic(topic, category="article", status="draft")
    article_id = await db.add_article(topic_id, body,
                                      image_path=image_path,
                                      image_prompt=img_prompt,
                                      length_hint=length_hint)
    logger.info("Статья #%s создана (topic #%s, image=%s)",
                article_id, topic_id, bool(image_path))
    return {
        "ok": True,
        "article_id": article_id,
        "topic_id": topic_id,
        "topic": topic,
        "body": body,
        "image_path": image_path,
        "reason": None,
    }
