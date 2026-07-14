"""Промпты для Gemini: статья, картинка, автоцензура, классификация комментов.

ID моделей — только через config/.env, здесь не хардкодим.
"""
import hashlib

# Тематика канала SMOKTOLK
NICHE = (
    "вейпы, электронные сигареты, кальяны, табак, "
    "безникотиновые альтернативы, культура и история курения"
)

# ── Генерация статьи ──────────────────────────────────────────────
def daytime_label(hour: int) -> str:
    """Метка времени суток по часу (0-23)."""
    if 5 <= hour < 11:
        return "утро"
    if 11 <= hour < 17:
        return "день"
    if 17 <= hour < 23:
        return "вечер"
    return "ночь"


ARTICLE_SYSTEM = (
    "Ты — автор познавательного Telegram-канала SMOKTOLK о культуре "
    f"курения: {NICHE}. Пишешь живо, экспертно, с уважением к читателю. "
    "Тон: умный, ироничный, без морализаторства и без назойливой рекламы."
)

# ЗАПРЕТЫ автоцензуры (важно для генерации и для проверки)
CENSOR_RULES = (
    "СТРОГИЕ ЗАПРЕТЫ:\n"
    "- НЕ призывай покупать, заказывать, «брать» товар (никаких call-to-action на покупку).\n"
    "- НЕ призывай начинать/продолжать употребление никотина или курить.\n"
    "- НЕ давай медицинских советов и не ставь диагнозов.\n"
    "- НЕ утверждай, что курение/вейпинг безопасны или полезны, а также не утверждай обратного.\n"
    "РАЗРЕШЕНО: упоминать бренды и модели нейтрально, в познавательном контексте."
)


def article_prompt(topic: str, used_topics: list[str] | None = None,
                   extra_rules: str | None = None,
                   length_hint: str | None = None,
                   daytime: str | None = None) -> str:
    used = ""
    daytime_line = (
        f"\nСЕЙЧАС: {daytime} (по местному времени UTC+5). "
        "Учитывай это в подаче и настроении. "
        "ВАЖНО: если используешь приветствие — оно ДОЛЖНО "
        f"соответствовать времени суток ({daytime}). "
        "НЕ пиши «Доброе утро», если сейчас не утро; "
        "НЕ пиши «Добрый вечер», если сейчас не вечер. "
        "Лучше вообще без приветствия, чем с неверным.\n"
        if daytime else ""
    )
    if used_topics:
        joined = "; ".join(used_topics)
        used = (
            "\n\nВСЕ УЖЕ ОПУБЛИКОВАННЫЕ ТЕМЫ (не повторяй их и близкие по смыслу):\n"
            f"{joined}"
        )
    # Длину/формат ВСЕГДА задаёт бот через length_hint
    # (facts_rules/words_rule/кастом). В базовом промпте длины НЕТ.
    length_line = (length_hint + "\n") if length_hint else ""
    extra = f"\n\nДОПОЛНИТЕЛЬНЫЕ ПРАВИЛА РЕДАКЦИИ:\n{extra_rules}" if extra_rules else ""
    return (
        f"{ARTICLE_SYSTEM}\n"
        f"{daytime_line}\n"
        f"Напиши статью на тему: «{topic}».\n"
        f"{length_line}"
        "Формат: HTML для Telegram (<b>жирный</b>, <i>курсив</i>, "
        "переносы строк). НЕ используй Markdown, НЕ используй теги <h1>-<h6>, "
        "<ul>, <li> — только <b>, <i>, <u>, <a>, эмодзи и переносы строк.\n"
        f"{CENSOR_RULES}"
        f"{used}"
        f"{extra}\n\n"
        "Верни ТОЛЬКО текст статьи, без пояснений и без служебных пометок."
    )


def topic_prompt(used_topics: list[str] | None = None) -> str:
    used = ""
    if used_topics:
        joined = "; ".join(used_topics[-100:])
        used = f"\n\nНЕ предлагай эти и похожие темы:\n{joined}"
    return (
        "Придумай одну свежую тему для статьи Telegram-канала о курении "
        f"({NICHE}).\n\n"
        "Тема ОБЯЗАНА быть про один из конкретных предметов ниши:\n"
        "- устройства: вейпы, под-системы, электронные сигареты, "
        "испарители, койлы, кальяны, чаши, колбы, шланги;\n"
        "- расходники: жидкости для вейпа, соль/фрибейз, табак для "
        "кальяна, угли, ароматизаторы, безникотиновые смеси;\n"
        "- практика: обзоры и сравнения, забивка кальяна, обслуживание "
        "устройств, лайфхаки, безопасность и здоровье;\n"
        "- культура и история: происхождение кальяна/табака, традиции, "
        "бренды, интересные факты именно о курении.\n\n"
        "СТРОГО ЗАПРЕЩЕНО: абстрактные темы, символика, эмодзи, "
        "жесты, психология, эзотерика, «скрытые смыслы», философия — "
        "если тема не про реальные вейпы/кальяны/табак, она НЕ подходит."
        f"{used}\n\n"
        "Верни ТОЛЬКО название темы одной строкой, без кавычек и пояснений."
    )


# ── Картинка ──────────────────────────────────────────────────────
_IMG_SCENES = [
    "close-up macro shot with shallow depth of field",
    "flat-lay top-down composition on a textured surface",
    "wide atmospheric interior scene with warm ambient light",
    "dramatic side lighting against a dark background",
    "minimalist still life on a clean neutral backdrop",
    "vintage retro aesthetic with film-grain texture",
    "moody nightlife setting with neon accents",
    "cozy evening scene with soft bokeh lights",
]
_IMG_PALETTES = [
    "warm amber and deep brown tones",
    "cool teal and smoky grey palette",
    "rich emerald and gold accents",
    "muted pastel colours",
    "high-contrast black and white with a single accent colour",
    "sunset orange and purple gradient",
]


def image_prompt(topic: str) -> str:
    """Вариативный промпт: сцена и палитра зависят от темы (детерминированно),
    чтобы разные статьи получали визуально разные картинки.
    """
    h = int(hashlib.md5(topic.encode("utf-8")).hexdigest(), 16)  # noqa: S324
    scene = _IMG_SCENES[h % len(_IMG_SCENES)]
    palette = _IMG_PALETTES[(h // 7) % len(_IMG_PALETTES)]
    return (
        "CRITICAL: absolutely NO TEXT anywhere in the image. "
        "No letters, no words, no captions, no titles, no headlines, "
        "no signage, no typography, no writing. Book spines and labels "
        "must be blank or blurred with no readable characters. "
        "This is a purely visual wordless photographic illustration. "
        "The scene must FILL THE ENTIRE FRAME edge to edge — "
        "absolutely NO white bars, NO black bars, NO borders, NO empty margins, "
        "NO letterboxing, NO padding; the subject and background "
        "extend fully to all four edges. "
        "High-quality editorial illustration for an article "
        f"about: {topic}. Theme: smoking culture (vapes, hookah, tobacco). "
        f"Composition: {scene}. Colour palette: {palette}. "
        "Stylish, cinematic, magazine cover quality. "
        "No logos, no watermarks, no people's faces in focus."
    )


# ── Автоцензура (проверка готового текста) ────────────────────────
def censor_prompt(article: str) -> str:
    return (
        "Проверь текст статьи на нарушения правил ниже.\n\n"
        f"{CENSOR_RULES}\n\n"
        "Если нарушений НЕТ — верни строку: OK\n"
        "Если нарушения ЕСТЬ — верни исправленный вариант ВСЕЙ статьи "
        "(сохрани HTML-разметку и объём), убрав нарушения. "
        "Больше ничего не добавляй.\n\n"
        f"ТЕКСТ:\n{article}"
    )


# ── Классификация комментариев ────────────────────────────────────
def classify_comment_prompt(comment: str) -> str:
    return (
        "Классифицируй комментарий из Telegram-обсуждения канала о культуре "
        "курения. Категории (верни РОВНО одно слово):\n"
        "- reklama — реклама, спам, ссылки на продажу, «продам/куплю»\n"
        "- toxic — оскорбления, троллинг, разжигание\n"
        "- question — вопрос по теме\n"
        "- neutral — нейтральное сообщение по теме\n"
        "- positive — благодарность, похвала, позитив\n\n"
        f"КОММЕНТАРИЙ: {comment}\n\n"
        "Ответ (одно слово):"
    )


def reply_comment_prompt(comment: str, category: str) -> str:
    style = {
        "question": "Ответь по существу, экспертно и остроумно.",
        "neutral": "Поддержи разговор остроумной репликой по теме.",
        "positive": "Тепло поблагодари, коротко и с юмором.",
    }.get(category, "Ответь остроумно и по теме.")
    return (
        f"Ты — ведущий канала SMOKTOLK о культуре курения. {style}\n"
        f"{CENSOR_RULES}\n"
        "Ответ короткий (1–3 предложения), живой, без хэштегов.\n\n"
        f"КОММЕНТАРИЙ: {comment}\n\n"
        "Твой ответ:"
    )


# ── Правила длины для generate_article (передаются как extra_rules) ──
def facts_rules(n: int) -> str:
    """Утро (08:00-10:00): короткий позитивный пост с фактами."""
    n = max(1, min(3, n))
    return (
        "ЭТО ПОСТ-ПОДБОРКА ФАКТОВ. СТРОГО СОБЛЮДАЙ ФОРМАТ, "
        "он ПОЛНОСТЬЮ ОТМЕНЯЕТ любые прежние указания об объёме. "
        "ОБЯЗАТЕЛЬНО перепроверь длину поста перед ответом:\n"
        f"- Дай {n} коротких любопытных факта по теме "
        "(нумерованный список цифрами 1., 2., 3.).\n"
        "- Факты могут быть из разных областей: открытия, "
        "заблуждения, мифы, свежие новости, научные исследования, "
        "факты из биографий, фильмов, мультфильмов, книг, байопиков, "
        "цитаты и случаи из жизни известных людей.\n"
        "- ВАЖНО: факты должны быть РЕАЛЬНЫМИ — находи их, "
        "а НЕ выдумывай. Разрешено только творчески переработать "
        "формулировку, чтобы она соответствовала правилам публикации.\n"
        "- Каждый факт — 1-2 предложения, живо и понятно.\n"
        "- ОБЯЗАТЕЛЬНО заверши пост короткой остроумной ШУТКОЙ по теме "
        "(1-2 предложения) — это финал поста, он должен вызвать улыбку "
        "и хорошее настроение.\n"
        "- Тон: лёгкий, тёплый, чуть ироничный, приятный для чтения.\n"
        "- ОБЩИЙ ОБЪЁМ ПОСТА: 100-150 слов, НЕ БОЛЬШЕ.\n"
        "- НЕ пиши длинных абзацев, НЕ используй подзаголовки, "
        "НЕ делай развёрнутую статью."
    )


def words_rule(words: int) -> str:
    """Вечер (19:00-20:30): вдумчивый лонг-рид на расслабление."""
    words = max(200, min(500, words))
    return (
        "ЭТО ЛОНГ-РИД. СТРОГО СОБЛЮДАЙ ФОРМАТ, "
        "он ПОЛНОСТЬЮ ОТМЕНЯЕТ любые прежние указания об объёме. "
        "ОБЯЗАТЕЛЬНО перепроверь длину поста перед ответом:\n"
        f"- Объём: {words} слов (диапазон 200-500, НЕ БОЛЬШЕ 500).\n"
        "- Формат: вдумчивый лонг-рид, который приятно "
        "почитать для расслабления.\n"
        "- Структура: спокойное вступление, 1-2 смысловых блока, "
        "мягкий вывод.\n"
        "- Тон: неспешный, атмосферный, познавательный, без суеты."
    )


def custom_words_rule(words: int | None, default: int = 150) -> str:
    """Статья по заказу: верхний лимит слов, без нижней границы."""
    n = default if not words or words < 1 else min(words, 800)
    return (
        "ФОРМАТ ПО ЗАКАЗУ. Это указание об объёме ПОЛНОСТЬЮ ОТМЕНЯЕТ "
        "любые прежние правила длины. ОБЯЗАТЕЛЬНО перепроверь длину "
        "перед ответом:\n"
        f"- Объём: НЕ БОЛЕЕ {n} слов (no more than {n} words). "
        "Можно короче, но НЕ длиннее.\n"
        "- Пиши строго по заданной теме/заданию пользователя.\n"
        "- Тон: живой, познавательный, по делу."
    )


def image_scene_prompt(body: str) -> str:
    """LLM извлекает из статьи короткое EN-описание визуальной сцены."""
    snippet = body[:1500]
    return (
        "You are an art director. Read the article below and describe, "
        "in ONE English sentence (max 25 words), a concrete photographic "
        "scene that visually represents its MAIN topic. "
        "Include subject, setting, mood and a colour palette. "
        "Do NOT mention text, letters or captions. Output only the sentence.\n\n"
        f"ARTICLE:\n{snippet}"
    )


def image_prompt_from_scene(scene: str, topic: str) -> str:
    """Технический каркас image_prompt, но сцена из текста статьи."""
    scene = " ".join(scene.split())[:300]
    return (
        "CRITICAL: absolutely NO TEXT anywhere in the image. "
        "No letters, no words, no captions, no titles, no headlines, "
        "no signage, no typography, no writing. Book spines and labels "
        "must be blank or blurred with no readable characters. "
        "This is a purely visual wordless photographic illustration. "
        "The scene must FILL THE ENTIRE FRAME edge to edge - "
        "absolutely NO white bars, NO black bars, NO borders, NO empty margins, "
        "NO letterboxing, NO padding; the subject and background "
        "extend fully to all four edges. "
        f"High-quality editorial illustration for an article about: {topic}. "
        "Theme: smoking culture (vapes, hookah, tobacco). "
        f"Scene: {scene} "
        "Stylish, cinematic, magazine cover quality. "
        "No logos, no watermarks, no people's faces in focus."
    )


# ===== U6.2/U6.3: Stories =====
STORY_THEMES = {
    1: "остроумная короткая шутка про культуру курения",
    2: "свежая новость индустрии (вейпы, кальяны, табак, регулирование)",
    3: "новинки рынка: устройства, вкусы, бренды (нейтрально, без рекламы)",
    4: "любопытный факт из истории или культуры курения",
    5: "доброе пожелание подписчикам канала",
}


def story_text_prompt(theme: int, search_snippet: str = "") -> str:
    """Текст для сторис канала @SMOKTOLK. Короткий, без призывов."""
    topic = STORY_THEMES.get(theme, STORY_THEMES[4])
    base = (
        "Ты ведёшь Telegram-канал @SMOKTOLK о культуре курения "
        "(вейпы, кальяны, табак). Составь ОЧЕНЬ короткий текст для Stories "
        f"на тему: {topic}. "
        "15-40 слов, живой разговорный тон, 1-2 эмодзи. "
        "Никаких призывов покупать/курить, никаких медсоветов. "
        "Верни только сам текст сторис, без пояснений.\n\n"
        + CENSOR_RULES
    )
    if search_snippet:
        base += f"\n\nОпирайся на актуальные данные:\n{search_snippet[:1500]}"
    return base


def story_flood_caption_prompt(theme: int, search_snippet: str = "") -> str:
    """Подпись для реюза картинки во flood-группе: интересный факт 20-50 слов."""
    topic = STORY_THEMES.get(theme, STORY_THEMES[4])
    base = (
        "Напиши интересный факт по теме "
        f"«{topic}» для подписи к сторис. "
        "Строго 20-50 слов, познавательно, без призывов покупать/курить, "
        "без медсоветов. 1 эмодзи допустимо. Верни только текст.\n\n"
        + CENSOR_RULES
    )
    if search_snippet:
        base += f"\n\nАктуальные данные:\n{search_snippet[:1500]}"
    return base


def story_image_prompt(scene: str) -> str:
    """NanoBanana-промпт для вертикальной сторис 9:16 (1080x1920).

    В отличие от постов, здесь ТЕКСТ на картинке РАЗРЕШЁН и на русском —
    крупный, читаемый, без артефактов.
    """
    scene = " ".join(scene.split())[:400]
    return (
        "Vertical Stories format, portrait 9:16 aspect ratio, 1080x1920 pixels. "
        "The image MUST fill the entire vertical frame edge to edge - "
        "no black bars, no white bars, no borders, no letterboxing. "
        f"Scene: {scene} "
        "Theme: smoking culture (vapes, hookah, tobacco), stylish, cinematic, "
        "modern social-media Stories aesthetic, vivid colours. "
        "If any text is shown, it MUST be in correct RUSSIAN, large, "
        "highly legible, clean sans-serif, perfectly spelled, no gibberish, "
        "no distorted letters, no artefacts. "
        "No logos, no watermarks, no faces in sharp focus."
    )
