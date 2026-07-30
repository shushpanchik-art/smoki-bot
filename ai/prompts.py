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
        "Проверь также ФАКТЫ: удали выдуманные названия веществ, "
        "несуществующие термины и недостоверные утверждения.\n"
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
    if n == 1:
        count_rule = ("- Дай РОВНО 1 короткий любопытный факт по теме, "
                      "БЕЗ нумерации и без списка.\n")
    else:
        count_rule = (f"- Дай РОВНО {n} коротких любопытных факта(ов) "
                      f"по теме нумерованным списком (1., 2. ...), "
                      f"НЕ больше и НЕ меньше {n}.\n")
    return (
        count_rule +
        "ЭТО ПОСТ-ПОДБОРКА ФАКТОВ. СТРОГО СОБЛЮДАЙ ФОРМАТ, "
        "он ПОЛНОСТЬЮ ОТМЕНЯЕТ любые прежние указания об объёме. "
        "ОБЯЗАТЕЛЬНО перепроверь длину поста перед ответом:\n"
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


def story_hook_prompt(caption: str) -> str:
    """Короткая затравка (5-9 слов) для наложения на картинку сторис."""
    return (
        "Ниже текст сторис. Придумай к нему ОЧЕНЬ короткую цепляющую "
        "затравку-заголовок для наложения на картинку.\n"
        "Строго 5-9 слов, БЕЗ хэштегов, БЕЗ кавычек, можно 1 эмодзи. "
        "Это анонс-интрига, а не пересказ. Верни ТОЛЬКО затравку.\n\n"
        f"Текст сторис:\n{caption[:800]}"
    )


def story_image_prompt(scene: str) -> str:
    """NanoBanana-промпт для вертикальной сторис 9:16 (1080x1920).

    scene — краткое описание визуальной СЦЕНЫ (фон, объекты, настроение).
    Текст на картинку НЕ наносится — его накладывает Pillow через
    services.story_render.render_story_caption. Поэтому картинка всегда
    генерируется без единой буквы (модель не умеет писать русский текст).
    """
    scene = " ".join(scene.split())[:400]
    parts = [
        "Vertical Stories format, portrait 9:16 aspect ratio, 1080x1920 pixels. ",
        "The image MUST fill the entire vertical frame edge to edge - ",
        "no black bars, no white bars, no borders, no letterboxing. ",
        f"Scene: {scene} ",
        "Theme: smoking culture (vapes, hookah, tobacco), stylish, cinematic, ",
        "modern social-media Stories aesthetic, vivid colours. ",
        "CRITICAL: absolutely NO TEXT anywhere in the image. ",
        "No letters, no words, no captions, no signs, no gibberish, "
        "no watermarks, no logos. ",
        "No faces in sharp focus.",
    ]
    return "".join(parts)
# ==================== САГА (многосерийный бизнес-триллер) ====================

SAGA_SYSTEM = (
    "Ты — автор захватывающей многосерийной саги для Telegram-канала "
    "@SMOKTOLK. Жанр: бизнес-триллер с элементами сарказма и социальной "
    "иронии. Действие разворачивается во вселенной индустрии курения: "
    "производители вейпов и жидкостей, дистрибьюторы, табачные бренды, "
    "регуляторы и проверки, серый импорт и чёрный рынок, войны и союзы "
    "игроков рынка, деньги, амбиции и предательства.\n\n"
    "СТИЛЬ И АТМОСФЕРА:\n"
    "- Язык живой, резкий, с сарказмом и социальной иронией. Современные "
    "реалии: гаджеты, соцсети, бренды, бизнес-лексика, циничные наблюдения "
    "о жизни, короткие хлёсткие диалоги.\n"
    "- Темп высокий: плотность событий, минимум воды, постоянное движение "
    "сюжета. Описания — только значимые детали (дорогие часы, запах пара в "
    "переговорной, надпись на экране телефона, пломба на контейнере с "
    "картриджами).\n"
    "- Форму повествования (первое или третье лицо) выбирают один раз и "
    "держат всю сагу неизменной.\n"
    "- Избегай буквальных переводов английских идиом, используй "
    "естественные русские обороты.\n"
)

SAGA_HARMON = (
    "КРУГ ХАРМОНА (тебе передают текущую стадию — встрой эпизод так, чтобы "
    "он двигал арку вперёд по этой стадии):\n"
    "1-Ты: обычный мир героя, статус-кво.\n"
    "2-Нужда: зарождение желания, неудовлетворённость.\n"
    "3-Порог: шаг в неизвестность, решение действовать.\n"
    "4-Поиск: испытания, союзники, враги, сбор ресурсов.\n"
    "5-Находка: кризис/откровение, переломный момент арки.\n"
    "6-Цена: последствия находки, тяжёлый выбор, потеря.\n"
    "7-Возвращение: герой возвращается в привычный мир изменившимся.\n"
    "8-Изменение: фиксация новой реальности; одновременно начало новой "
    "арки (обновлённое «Ты» героя).\n"
    "Если стадия не передана — считай, что ты в середине «4-Поиск».\n"
)

SAGA_RULES = (
    "ЖЁСТКИЕ ПРАВИЛА:\n"
    "1. НЕ используй эмодзи. Формат Telegram HTML: <b>, <i>, абзацы через "
    "пустую строку. Без Markdown, без #, без *.\n"
    "2. Непрерывность: имена, характеры, статусы и локации ТОЧНО "
    "соответствуют хронике ниже. Не противоречь прошлым событиям, ничего "
    "не забывай.\n"
    "3. Новый персонаж не возникает «из ниоткуда»: сначала покажи его "
    "через звонок, сообщение, упоминание или деталь — и только потом вводи "
    "в действие. То же с новыми локациями.\n"
    "4. Каждый эпизод — по пирамиде Фрейтага: экспозиция (кратко или через "
    "действие) → завязка → развитие → кульминация → обрыв (без полного "
    "разрешения).\n"
    "5. ХОЛОДНЫЙ СТАРТ (cold open): первое предложение — яркое событие, "
    "прямое продолжение прошлого клиффхэнгера или шокирующая деталь. НЕ "
    "начинай с погоды или долгих рассуждений.\n"
    "6. КРЮЧКИ: заложи 2-3 детали-обещания будущих событий (странная "
    "фраза, незаконченное действие, многозначительный взгляд, артефакт). "
    "Могут не раскрыться в этом эпизоде.\n"
    "7. КОНТРАСТ ТОНАЛЬНОСТЕЙ: чередуй напряжённые сцены со спокойными, но "
    "содержательными (диалог, смена локации, флешбэк) — избегай "
    "монотонности.\n"
    "8. ПАРАЛЛЕЛЬНЫЕ ЛИНИИ: если есть побочные сюжеты — хотя бы кратко "
    "напомни о них, чтобы не забывались; новые связывай с основным "
    "конфликтом.\n"
    "9. ЭМОЦИИ: показывай внутренние переживания героя через действия и "
    "детали (угроза потери статуса, страх разоблачения, жажда мести, "
    "уязвимость) — заставляй сопереживать.\n"
    "10. КЛИФФХЭНГЕР: последние 1-3 предложения обрывают повествование на "
    "пике саспенса. Формы: буквальное прерывание с указанием угрозы «в "
    "дверях стоял тот, кого он похоронил полгода назад…»; неразрешённый "
    "вопрос «кто прислал сообщение с его же номера?»; внезапная смена "
    "обстоятельств «экран погас, и свет в кабинете мигнул навсегда»; "
    "эмоциональный шок «она улыбнулась, и Воронцов понял — это конец».\n"
    "11. ЯЗЫК: весь текст, включая авторскую речь и диалоги, строго на "
    "русском языке. Иностранные слова допустимы только в именах "
    "собственных, названиях брендов и заведений.\n"
)

SAGA_CHARS_RULE = (
    "ПЕРСОНАЖИ И ЛОКАЦИИ:\n"
    "- Ключевых (main) персонажей — НЕ больше 3. Второстепенных "
    "(secondary) — НЕ больше 5. Проходных (transient) — сколько угодно.\n"
    "- Действия персонажей мотивированы их установленными характерами и "
    "статусами.\n"
    "- После эпизода обнови словари: добавь новых, обнови статусы "
    "существующих (получил компромат, уехал, ранен, предал). Описывай так, "
    "чтобы следующий эпизод опирался без противоречий.\n"
)

SAGA_META_RULE = (
    "ФОРМАТ ОТВЕТА (СТРОГО):\n"
    "Сначала — текст эпизода (600-1000 слов). Затем на ОТДЕЛЬНОЙ строке: "
    "===META===\n"
    "Затем ОДИН валидный JSON без комментариев и без текста после него:\n"
    "{\n"
    '  "summary": "2-5 предложений: ключевое событие (что изменилось в '
    'сюжете) + эмоциональный вектор героя + открытые вопросы и новые '
    'крючки",\n'
    '  "narration": "первое лицо" | "третье лицо",\n'
    '  "characters": {"main": [{"name":"", "role":"", "status":""}], '
    '"secondary": [...], "transient": [...]},\n'
    '  "locations": [{"name":"", "desc":""}],\n'
    '  "harmon_stage": "4-Поиск",\n'
    '  "arc_number": 1,\n'
    '  "arc_goal": "главная цель/конфликт этой арки",\n'
    '  "arc_plan": ["шаг1", "шаг2", "..."],\n'
    '  "planned_arc_length": 6,\n'
    '  "episode_in_arc": 1,\n'
    '  "arc_status": "in_progress" | "completed",\n'
    '  "pending_arc_seed": "зародыш следующей арки (если завершаешь эту)"\n'
    "}\n"
    "characters и locations — ПОЛНЫЕ актуальные словари (бот заменяет "
    "старые целиком). Ничего не пиши после закрывающей }.\n"
)


def _saga_memory(state: dict | None, summaries: list[dict] | None) -> str:
    """Компактная память: синопсисы завершённых арок + последние 2-3
    summary + текущие персонажи/локации. НЕ вся хроника целиком."""
    import json as _json
    if not state:
        return "ПЕРВЫЙ ЭПИЗОД. Хроники ещё нет."
    parts: list[str] = []
    syn_raw = state.get("arc_synopsis_json") or "[]"
    try:
        synopses = _json.loads(syn_raw)
    except Exception:
        synopses = []
    if synopses:
        lines = "\n".join(
            f"- Арка {i + 1}: {s}" for i, s in enumerate(synopses))
        parts.append("СИНОПСИСЫ ЗАВЕРШЁННЫХ АРОК:\n" + lines)
    recent = (summaries or [])[-3:]
    if recent:
        lines = "\n".join(
            f"- Эп.{r.get('episode_number', '?')} "
            f"(арка {r.get('arc_number', '?')}): {r.get('summary', '')}"
            for r in recent)
        parts.append("ПОСЛЕДНИЕ ЭПИЗОДЫ:\n" + lines)
    chars = state.get("characters_json") or "{}"
    locs = state.get("locations_json") or "[]"
    parts.append(
        "АКТУАЛЬНЫЕ ПЕРСОНАЖИ (обнови этот JSON и верни в meta.characters, "
        "соблюдая лимиты main<=3, secondary<=5):\n" + chars)
    parts.append(
        "АКТУАЛЬНЫЕ ЛОКАЦИИ (обнови этот JSON и верни в meta.locations):\n"
        + locs)
    return "\n\n".join(parts)


def saga_prompt(state: dict | None,
                summaries: list[dict] | None = None,
                force_finale: bool = False) -> str:
    """Промт для генерации очередного эпизода саги.

    state: dict из get_saga_state() или None (самый первый эпизод).
    summaries: список dict прошлых summary (для компактной памяти).
    force_finale: True если арка затянулась (episode_in_arc >= 8).
    """
    memory = _saga_memory(state, summaries)

    if not state:
        situation = (
            "ЭТО ПЕРВЫЙ ЭПИЗОД. Придумай мир в индустрии курения, главных "
            "героев (имена, характеры, статусы), место действия и цель "
            "арки №1. Составь план арки на 6-8 эпизодов. Выбери форму "
            "повествования (первое или третье лицо) — держи её всю сагу. "
            "Начни арку со стадии «1-Ты».\n"
        )
    else:
        eia = int(state.get("episode_in_arc") or 0)
        arc_n = state.get("arc_number", 1)
        goal = state.get("arc_goal") or "(не задана)"
        stage = state.get("harmon_stage") or "4-Поиск"
        narr = state.get("narration") or "выбрана ранее — сохрани её"
        situation = (
            f"ФОРМА ПОВЕСТВОВАНИЯ: {narr} (не меняй).\n"
            f"ТЕКУЩАЯ АРКА: №{arc_n}. Цель: «{goal}». "
            f"Стадия Хармона: {stage}. Это эпизод №{eia + 1} в арке.\n"
        )
        if force_finale:
            situation += (
                "\nВНИМАНИЕ: арка затянулась. ЭТО ФИНАЛЬНЫЙ ЭПИЗОД АРКИ. "
                "Доведи главный конфликт арки до кульминации и развязки — "
                "без рояля в кустах, органично. Оставь РОВНО ОДНУ "
                "недосказанную линию как зацепку для следующей арки. "
                'Поставь "arc_status":"completed" и заполни '
                '"pending_arc_seed".\n')
        elif eia + 1 >= (state.get("planned_arc_length") or 6):
            situation += (
                "\nАрка близится к финалу — начинай сводить главный "
                "конфликт к развязке в ближайших 1-2 эпизодах.\n")

    return (
        f"{SAGA_SYSTEM}\n"
        f"{SAGA_HARMON}\n"
        f"{SAGA_RULES}\n"
        f"{SAGA_CHARS_RULE}\n"
        f"{situation}\n"
        f"ХРОНИКА (не противоречь!):\n{memory}\n\n"
        f"{SAGA_META_RULE}"
    )
