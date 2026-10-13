# System Design Document (DESIGN)
## SMOKI-bot — Архитектура системы

**Версия:** 1.0  
**Дата:** 13 октября 2026  
**Связанные документы:** [PRD.md](PRD.md), [TRD.md](TRD.md), [DB.md](DB.md)

---

## 1. Обзор архитектуры

### 1.1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SERVICES                         │
├─────────────────────────────────────────────────────────────────┤
│  Telegram Bot API  │  Google Vertex AI  │  Serper News API     │
│  (Bot + Channel)   │  (Gemini + Imagen) │  (News Search)       │
└──────────┬─────────┴──────────┬──────────┴──────────┬───────────┘
           │                    │                     │
           v                    v                     v
┌─────────────────────────────────────────────────────────────────┐
│                         SMOKI-BOT SERVICE                        │
│                    (Python 3.11, aiogram 3.x)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐ │
│  │   Bot Core     │  │   Scheduler    │  │   AI Services    │ │
│  │   (bot.py)     │  │ (APScheduler)  │  │  (ai/gemini.py)  │ │
│  └────────┬───────┘  └────────┬───────┘  └────────┬─────────┘ │
│           │                   │                    │            │
│  ┌────────┴──────────────┬────┴────────────────────┴─────────┐ │
│  │                       │                                    │ │
│  │  ┌──────────────┐    │    ┌──────────────┐              │ │
│  │  │  Handlers    │    │    │  Services    │              │ │
│  │  │  (модули)    │◄───┼───►│  (бизнес-    │              │ │
│  │  │              │    │    │   логика)    │              │ │
│  │  └──────────────┘    │    └──────────────┘              │ │
│  │                      │                                    │ │
│  └──────────────────────┴────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │              Database Layer (db/database.py)              │ │
│  │                   SQLite + APScheduler jobstore           │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
           │
           v
┌─────────────────────────────────────────────────────────────────┐
│                     PERSISTENT STORAGE                           │
├─────────────────────────────────────────────────────────────────┤
│  data/smoki.db (SQLite)  │  data/images/*.png  │  .env (secrets)│
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Компоненты системы

### 2.1. Bot Core (`bot.py`)

**Назначение:** Точка входа приложения, инициализация всех компонентов.

**Основные функции:**
- Инициализация aiogram Bot + Dispatcher
- Регистрация handlers (admin, moderation, errors)
- Запуск scheduler (APScheduler)
- Запуск polling loop
- Graceful shutdown (закрытие aiohttp сессий)

**Lifecycle:**
```python
async def main():
    # 1. Init DB
    await init_db()
    
    # 2. Init bot + dispatcher
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    
    # 3. Register handlers
    dp.include_router(admin_router)
    dp.include_router(moderation_router)
    
    # 4. Start scheduler
    scheduler.start()
    
    # 5. Start polling
    await dp.start_polling(bot)
    
    # 6. Cleanup on exit
    finally:
        await close_session()
```

**Зависимости:**
- `config.py` — переменные окружения
- `db/database.py` — инициализация БД
- `handlers/` — обработчики команд и callback
- `scheduler.py` — планировщик задач
- `ai/search.py` — закрытие aiohttp сессии

---

### 2.2. Handlers Layer

#### 2.2.1. Admin Handler (`handlers/admin.py`)

**Назначение:** Панель управления для администратора.

**Endpoints (команды):**
```python
@router.message(Command("start"))        # Главная панель
@router.message(Command("generate"))     # Ручная генерация
@router.message(Command("generate_morning"))
@router.message(Command("generate_evening"))
@router.message(Command("setlen"))       # Настройка длины
@router.message(Command("stats"))        # Статистика AI
@router.message(Command("id"))           # Debug: показать chat_id
```

**Callbacks (кнопки):**
```python
@router.callback_query(F.data == "adm_gen")      # Обычный пост
@router.callback_query(F.data == "adm_gen_m")    # Утренний
@router.callback_query(F.data == "adm_gen_e")    # Вечерний
@router.callback_query(F.data == "adm_stats")    # Статистика
@router.callback_query(F.data == "adm_len")      # Длина постов
@router.callback_query(F.data == "adm_liked")    # Правила "нравится"
@router.callback_query(F.data == "adm_censor")   # Правила цензуры
@router.callback_query(F.data == "adm_comments") # Комментарии
@router.callback_query(F.data == "adm_schedule") # Расписания
@router.callback_query(F.data == "adm_backup")   # Бэкап
```

**FSM States:**
```python
class AdminStates(StatesGroup):
    waiting_custom_topic = State()    # Ждём ввода темы
    waiting_liked_edit = State()      # Ждём правил "нравится"
    waiting_censor_edit = State()     # Ждём правил цензуры
```

**Безопасность:**
- Проверка `message.from_user.id == ADMIN_CHAT_ID` на каждом endpoint
- Неавторизованным пользователям: "У вас нет доступа. Ваш ID: {user_id}"

---

#### 2.2.2. Moderation Handler (`handlers/moderation.py`)

**Назначение:** Обработка модерации черновиков (5 кнопок).

**Callbacks:**
```python
@router.callback_query(F.data.startswith("pub:"))       # ✅ Опубликовать
@router.callback_query(F.data.startswith("regen_text:")) # 🔄 Регенерировать текст
@router.callback_query(F.data.startswith("regen_image:"))# 🖼 Регенерировать картинку
@router.callback_query(F.data.startswith("edit:"))      # 📝 Редактировать (заглушка)
@router.callback_query(F.data.startswith("cancel:"))    # ⛔ Отмена
```

**Бизнес-логика:**
1. **Опубликовать:**
   - Вызов `services.publisher.publish_article(article_id)`
   - Обновление статуса: `pending` → `published`
   - Обновление черновика: "✅ Опубликовано в HH:MM"

2. **Регенерировать текст:**
   - Вызов `services.content.generate_article()` с той же темой
   - Сохранение старой картинки
   - Инкремент `regen_count` в БД
   - Отправка нового черновика

3. **Регенерировать картинку:**
   - Вызов `ai.gemini.generate_image()` с новым промптом
   - Сохранение старого текста
   - Инкремент `regen_count`
   - Обновление черновика

4. **Отмена:**
   - Обновление статуса: `pending` → `cancelled`
   - Сообщение: "Черновик #N отменён"

**Лимиты:**
- Максимум 10 регенераций на пост
- После 10 попыток: "Достигнут лимит попыток"

---

#### 2.2.3. Error Handler (`handlers/errors.py`)

**Назначение:** Глобальная обработка ошибок.

**Типы ошибок:**
```python
@router.error()
async def error_handler(event: ErrorEvent):
    if isinstance(event.exception, TelegramForbiddenError):
        # Бот заблокирован пользователем
        logger.warning("Bot blocked by user %s", event.update.user.id)
    
    elif isinstance(event.exception, TelegramRetryAfter):
        # Rate limit exceeded
        await asyncio.sleep(event.exception.retry_after)
    
    else:
        # Неизвестная ошибка
        logger.exception("Unhandled error")
        # Алерт админу (если критично)
```

---

### 2.3. Services Layer (бизнес-логика)

#### 2.3.1. Content Service (`services/content.py`)

**Назначение:** Генерация статей (текст + картинка + автоцензура).

**Главная функция:**
```python
async def generate_article(
    topic: str | None = None,
    extra_rules: str | None = None,
    length_hint: str | None = None,
    make_image: bool = True
) -> dict:
    """
    Returns:
        {
            "ok": True/False,
            "article_id": int,
            "topic": str,
            "body": str,
            "image_path": str,
            "reason": str (если ok=False)
        }
    """
```

**Pipeline (8 шагов):**
```
1. Генерация темы (если не задана)
   ├─> generate_topic() → topic
   └─> Проверка дублей (published_topics)

2. Правило длины (length_hint)
   ├─> Утро: facts_rules(n) — "1-3 факта + шутка"
   └─> Вечер: words_rule(w) — "200-500 слов"

3. Накопленный опыт
   ├─> liked_feedback (стиль админа)
   ├─> censor_extra (замечания цензуры)
   └─> admin_feedback (если регенерация)

4. Hybrid News Search (опционально)
   ├─> _detect_news_topic(topic) → True/False
   ├─> ai.search.search_news() → list[NewsItem] | None
   └─> format_news_context() → контекст для промпта

5. Генерация текста
   ├─> prompts.article_prompt(topic, rules, context)
   ├─> ai.gemini.generate_text(use_search=True/False)
   └─> _clean_html(body) → чистка запрещённых тегов

6. Автоцензура
   ├─> services.censor.censor(body) → (ok, result)
   ├─> Если ok=False → return {"ok": False, "reason": ...}
   └─> Если ok=True → body = result (исправленный текст)

7. Генерация картинки (если make_image=True)
   ├─> prompts.image_scene_prompt(body) → EN-сцена
   ├─> prompts.image_prompt_from_scene(scene, topic) → промпт
   ├─> ai.gemini.generate_image(prompt) → PNG
   └─> _crop_landscape(image) → 4:5 портрет

8. Запись в БД
   ├─> db.save_topic(topic, category, status="draft")
   ├─> db.save_article(topic_id, body, image_path, ...)
   └─> return {"ok": True, "article_id": ..., ...}
```

**Fallback логика:**
- Hybrid search: Serper API → Google grounding
- Gemini: Vertex AI → AI Studio key
- Imagen: primary client → fallback client

---

#### 2.3.2. Censor Service (`services/censor.py`)

**Назначение:** Автоцензура статей перед публикацией.

**Функция:**
```python
async def censor(body: str) -> tuple[bool, str]:
    """
    Args:
        body: HTML-текст статьи
    
    Returns:
        (True, corrected_text)  — прошла цензуру (возможно с правками)
        (False, reason)         — НЕ прошла (причина нарушения)
    """
```

**Правила проверки:**
```python
CENSOR_RULES = """
ЗАПРЕЩЕНО:
- Призыв к покупке и курению
- Медицинские советы
- Утверждения о пользе курения
- Агрессивный тон

РАЗРЕШЕНО:
- Нейтральное упоминание брендов
- Образовательный контент
- Исторические факты
"""
```

**Промпт:**
```python
def censor_prompt(body: str, extra_rules: str) -> str:
    return f"""
Ты — цензор контента Telegram-канала о культуре курения.
Проверь статью на соответствие правилам.

ПРАВИЛА:
{CENSOR_RULES}
{extra_rules}

СТАТЬЯ:
{body}

ОТВЕТ:
- Если нарушений НЕТ → верни "OK"
- Если нарушения ЕСТЬ → исправь текст и верни ВЕСЬ исправленный текст
"""
```

**Логирование:**
- Каждая проверка логируется в `ai_logs` (kind='censor')
- Накопленные замечания → `settings.censor_extra`

---

#### 2.3.3. Publisher Service (`services/publisher.py`)

**Назначение:** Публикация статей в канал.

**Функция:**
```python
async def publish_article(article_id: int) -> dict:
    """
    Returns:
        {
            "ok": True/False,
            "message_id": int (если ok=True),
            "error": str (если ok=False)
        }
    """
```

**Логика разбивки:**
```python
if len(body) <= 1024:
    # Короткий текст → caption к картинке
    await bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=FSInputFile(image_path),
        caption=body,
        parse_mode=ParseMode.HTML
    )

elif len(body) <= 4096:
    # Средний текст → картинка отдельно + текст отдельно
    await bot.send_photo(chat_id=CHANNEL_ID, photo=...)
    await bot.send_message(chat_id=CHANNEL_ID, text=body, ...)

else:
    # Длинный текст → разбивка на N сообщений
    chunks = _split_text(body, max_length=4096)
    await bot.send_photo(...)
    for chunk in chunks:
        await bot.send_message(chat_id=CHANNEL_ID, text=chunk, ...)
```

**Обновление БД:**
```python
await db.update_article(
    article_id,
    status="published",
    message_id=result.message_id,
    published_at=datetime.now()
)
await db.update_topic(topic_id, status="published")
```

---

#### 2.3.4. Comments Moderator (`services/comments_moderator.py`)

**Назначение:** Автоматическая модерация комментариев.

**Главная функция:**
```python
async def process_new_comments() -> dict:
    """
    Обрабатывает все новые комментарии (status='new').
    
    Returns:
        {
            "processed": int,
            "deleted": int,
            "replied": int,
            "errors": int
        }
    """
```

**Pipeline:**
```
1. Получить новые комментарии (status='new' из БД)

2. Классификация (для каждого комментария)
   ├─> prompts.classify_comment(text) → класс
   └─> Классы: reklama, toxic, question, neutral, positive

3. Действия по классу:
   ├─> reklama / toxic → delete_message() + status='deleted'
   ├─> question / neutral → generate_reply() + send_message() + status='replied'
   └─> positive → status='replied' (без ответа)

4. Запись в БД:
   ├─> classification, bot_reply, processed_at
   └─> status → 'replied' | 'deleted' | 'error'
```

**Промпт классификации:**
```python
def classify_comment(text: str) -> str:
    prompt = f"""
Классифицируй комментарий в Telegram-канале о вейпах/кальянах:

КЛАССЫ:
- reklama: спам, реклама, ссылки на покупку
- toxic: оскорбления, мат, агрессия
- question: вопрос от пользователя
- neutral: обычный комментарий
- positive: благодарность, похвала

КОММЕНТАРИЙ: {text}

ОТВЕТ (одно слово):
"""
    return ai.gemini.generate_text(prompt, use_search=False)
```

---

### 2.4. AI Layer

#### 2.4.1. Gemini Client (`ai/gemini.py`)

**Назначение:** Обёртка над Google Gemini API (текст + изображения).

**Два клиента:**
```python
# Primary: Vertex AI (Workload Identity)
client = genai.Client(
    vertexai=True,
    project=GOOGLE_CLOUD_PROJECT,
    location=GOOGLE_CLOUD_LOCATION
)

# Fallback: AI Studio (API key)
fallback_client = genai.Client(
    api_key=GEMINI_API_KEY_FALLBACK
)
```

**Функции:**
```python
def generate_text(
    prompt: str,
    temperature: float = 0.7,
    max_output_tokens: int = 8192,
    use_search: bool = False
) -> str:
    """
    Args:
        use_search: True → Google Search grounding
    
    Returns:
        Generated text
    """
    # Sync function → вызывается через asyncio.to_thread()

def generate_image(
    prompt: str,
    aspect_ratio: str = "4:5"
) -> bytes | None:
    """
    Returns:
        PNG bytes (1024x1024 → cropped to 4:5)
        None (если оба клиента не сработали)
    """
```

**Автопереключение:**
```python
for client in [primary_client, fallback_client]:
    try:
        result = client.models.generate_content(...)
        return result.text
    except Exception as e:
        logger.warning("Client failed: %s", e)
        continue

# Оба упали
raise RuntimeError("All clients failed")
```

**Safety settings:**
```python
safety_settings = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    # Другие категории: BLOCK_NONE (разрешено для образовательного контента)
}
```

---

#### 2.4.2. Serper Search (`ai/search.py`)

**Назначение:** Поиск новостей через Serper News API.

**Главная функция:**
```python
async def search_news(
    query: str,
    days: int = 7,
    num_results: int = 5
) -> list[NewsItem] | None:
    """
    Returns:
        list[NewsItem] — найденные новости
        None — SERPER_API_KEY не задан (fallback на grounding)
        [] — ошибка API (fallback на grounding)
    """
```

**NewsItem структура:**
```python
class NewsItem(TypedDict):
    title: str
    snippet: str
    source: str
    date: str
    link: str
    imageUrl: str  # URL картинки новости (может быть пустой)
```

**HTTP клиент:**
```python
_session: aiohttp.ClientSession | None = None

def _get_session() -> aiohttp.ClientSession:
    """Ленивая инициализация (синглтон)."""
    global _session
    if _session is None:
        _session = aiohttp.ClientSession()
    return _session

async def close_session():
    """Вызывается в bot.py при shutdown."""
    global _session
    if _session is not None:
        await _session.close()
        _session = None
```

**Форматирование для промпта:**
```python
def format_news_context(news: list[NewsItem]) -> str:
    """
    Returns:
        АКТУАЛЬНЫЕ НОВОСТИ ПО ТЕМЕ:
        
        1. Заголовок новости 1
           Описание...
           Источник: Example.com, 2026-10-13
        
        2. Заголовок новости 2
           ...
    """
```

---

### 2.5. Database Layer

#### 2.5.1. Database Module (`db/database.py`)

**Назначение:** Async обёртка над SQLite через aiosqlite.

**Инициализация:**
```python
async def init_db():
    """
    1. Создаёт data/ если не существует
    2. Применяет schema.sql (CREATE TABLE IF NOT EXISTS)
    3. Запускает миграции (_migrate_saga, _migrate_story_jobs)
    """
```

**CRUD операции:**
```python
# Topics
async def save_topic(title, category, status) -> int
async def get_topic(topic_id) -> dict | None
async def get_recent_topics(limit=200) -> list[dict]

# Articles
async def save_article(topic_id, body, image_path, ...) -> int
async def get_article(article_id) -> dict | None
async def update_article(article_id, **fields) -> None
async def get_undelivered_today() -> list[dict]

# Comments
async def save_comment(chat_id, message_id, user_id, text) -> int
async def get_new_comments(limit=50) -> list[dict]
async def update_comment(comment_id, **fields) -> None

# Settings
async def get_setting(key, default=None) -> str | None
async def set_setting(key, value) -> None

# AI Logs
async def log_ai_call(kind, model, input_tokens, output_tokens, ...) -> None
async def get_ai_stats(month) -> dict

# Stats
async def get_stats() -> dict
```

**Connection pooling:**
```python
# Каждая функция открывает свой connection:
async with aiosqlite.connect(DB_PATH) as db:
    db.row_factory = aiosqlite.Row
    cursor = await db.execute("SELECT ...")
    rows = await cursor.fetchall()
    return rows

# SQLite не поддерживает connection pool — один процесс, sequential writes
```

---

#### 2.5.2. Schema (`db/schema.sql`)

**Таблицы:** См. [DB.md](DB.md) для полной схемы.

**Ключевые индексы:**
```sql
CREATE INDEX idx_articles_status ON articles(status);
CREATE INDEX idx_articles_created_at ON articles(created_at);
CREATE INDEX idx_comments_status ON comments(status);
CREATE INDEX idx_comments_processed_at ON comments(processed_at);
```

---

### 2.6. Scheduler (`scheduler.py`)

**Назначение:** Расписание автоматических задач (APScheduler).

**Jobstore:**
```python
jobstores = {
    'default': SQLAlchemyJobStore(url=f'sqlite:///{DB_PATH}')
}
# Persistent → пропущенные задачи выполняются после рестарта
```

**Задачи:**
```python
# 1. Утренний пост
scheduler.add_job(
    _job_morning,
    trigger=CronTrigger(hour=MORNING_START, minute=random_minute, timezone='Europe/Moscow'),
    id='daily_morning',
    replace_existing=True,
    misfire_grace_time=3600,
    coalesce=True,
    max_instances=1
)

# 2. Вечерний пост
scheduler.add_job(_job_evening, ...)

# 3. Дедлайн-автопубликация (2 запуска)
scheduler.add_job(_job_deadline, ..., id='publish_deadline')
scheduler.add_job(_job_deadline, ..., id='publish_deadline_evening')

# 4. Предупреждение перед дедлайном (2 запуска)
scheduler.add_job(_job_preview_warn, ..., id='preview_warn_day')
scheduler.add_job(_job_preview_warn, ..., id='preview_warn_evening')

# 5. Модерация комментариев
scheduler.add_job(
    _job_comments,
    trigger=IntervalTrigger(hours=COMMENTS_INTERVAL_HOURS),
    id='process_comments',
    ...
)

# 6. Heartbeat
scheduler.add_job(
    _job_heartbeat,
    trigger=IntervalTrigger(hours=HEARTBEAT_INTERVAL_HOURS),
    id='heartbeat',
    ...
)

# 7. Watchdog доставки
scheduler.add_job(_job_delivery_watchdog, ...)

# 8. Stories (если включены)
scheduler.add_job(_job_plan_stories_channel, ...)
scheduler.add_job(_job_send_pending_stories, ...)
```

**Управление задачами:**
```python
# Пауза (через настройки БД)
paused_jobs = await db.get_setting('paused_jobs', '')  # CSV: "daily_morning,daily_evening"
if job.id in paused_jobs.split(','):
    return  # Skip execution

# Изменение времени (через настройки БД)
custom_hour = await db.get_setting('time_daily_morning')
if custom_hour:
    scheduler.reschedule_job('daily_morning', trigger=CronTrigger(hour=int(custom_hour), ...))
```

---

## 3. Data Flow диаграммы

### 3.1. Генерация утреннего поста

```
[Scheduler: 08:XX MSK]
         │
         v
[_job_morning()]
         │
         ├─> Читает morning_facts из БД (1-3)
         ├─> length_hint = prompts.facts_rules(n)
         │
         v
[services.content.generate_article(length_hint=...)]
         │
         ├─> 1. generate_topic() → "Электронные сигареты новости октябрь 2026"
         │
         ├─> 2. _detect_news_topic() → True (новостная)
         │        ↓
         │   ai.search.search_news() → [NewsItem, NewsItem, ...]
         │        ↓
         │   format_news_context() → контекст для промпта
         │
         ├─> 3. prompts.article_prompt(topic, length_hint, context)
         │        ↓
         │   ai.gemini.generate_text(use_search=False) → HTML-текст
         │        ↓
         │   _clean_html() → очистка
         │
         ├─> 4. services.censor.censor(body)
         │        ↓
         │   (True, corrected_text) → ok
         │
         ├─> 5. ai.gemini.generate_image(prompt) → PNG
         │        ↓
         │   _crop_landscape() → 4:5 портрет
         │
         ├─> 6. db.save_topic(topic) → topic_id
         │   db.save_article(topic_id, body, image_path) → article_id
         │
         v
[handlers.admin.send_for_moderation(article_id)]
         │
         ├─> bot.send_photo(ADMIN_CHAT_ID, image, caption=body)
         ├─> InlineKeyboardMarkup: [✅ 🔄 🖼 📝 ⛔]
         │
         v
[Администратор нажимает ✅]
         │
         v
[handlers.moderation: pub:{article_id}]
         │
         v
[services.publisher.publish_article(article_id)]
         │
         ├─> bot.send_photo(CHANNEL_ID, image, caption=body)
         ├─> db.update_article(status="published", message_id=...)
         │
         v
[Пост опубликован в канале]
```

---

### 3.2. Автопубликация по дедлайну

```
[Scheduler: 10:00 MSK]
         │
         v
[_job_deadline()]
         │
         ├─> db.get_undelivered_today() → list[article]
         │        ↓
         │   [article #123: status=pending]
         │   [article #124: status=approved]
         │
         v
[Для каждой статьи]
         │
         ├─> services.publisher.publish_article(article_id)
         │        ↓
         │   bot.send_photo(CHANNEL_ID, ...)
         │        ↓
         │   db.update_article(status="published", ...)
         │
         v
[bot.send_message(ADMIN_CHAT_ID, summary)]
         │
         v
"✅ Автопубликация выполнена (10:00)
 Опубликовано автоматически: #123, #124"
```

---

### 3.3. Модерация комментариев

```
[Scheduler: каждые 6 часов]
         │
         v
[_job_comments()]
         │
         v
[services.comments_moderator.process_new_comments()]
         │
         ├─> db.get_new_comments(limit=50) → list[comment]
         │
         v
[Для каждого комментария]
         │
         ├─> prompts.classify_comment(text)
         │        ↓
         │   ai.gemini.generate_text() → класс
         │        ↓
         │   "reklama" / "toxic" / "question" / "neutral" / "positive"
         │
         v
[Действия по классу]
         │
         ├─> reklama/toxic:
         │        ├─> bot.delete_message(chat_id, message_id)
         │        └─> db.update_comment(status="deleted")
         │
         ├─> question/neutral:
         │        ├─> ai.gemini.generate_text(reply_prompt) → ответ
         │        ├─> bot.send_message(chat_id, reply_to=message_id)
         │        └─> db.update_comment(status="replied", bot_reply=...)
         │
         └─> positive:
                 └─> db.update_comment(status="replied")
```

---

## 4. Безопасность

### 4.1. Authentication & Authorization

**Telegram Bot:**
- BOT_TOKEN: секрет в `.env`, не коммитится
- ADMIN_CHAT_ID: whitelist администратора
- Все admin-команды проверяют `user.id == ADMIN_CHAT_ID`

**Google Cloud:**
- Workload Identity: service account без JSON-ключей
- Minimal IAM роль: `roles/aiplatform.user`
- Fallback: AI Studio API key в `.env`

**Serper API:**
- SERPER_API_KEY: опциональный, в `.env`
- Fallback: Google grounding при отсутствии

---

### 4.2. Data Protection

**Secrets:**
```bash
# .env (600 permissions, не в git)
BOT_TOKEN=...
ADMIN_CHAT_ID=...
SERPER_API_KEY=...
GEMINI_API_KEY_FALLBACK=...
```

**Database:**
- SQLite файл: `data/smoki.db` (600 permissions)
- Backup: ежедневный snapshot (GCP), retention 30 дней
- Нет персональных данных подписчиков (только comments от публичной группы)

**Logs:**
- Нет секретов в логах
- API ключи маскируются: `SERPER_API_KEY=***...***`

---

### 4.3. Content Safety

**Автоцензура:**
- 100% статей проходят проверку перед публикацией
- Запрещённые формулировки → регенерация (до 3 раз)
- Логирование всех нарушений

**Imagen safety filter:**
```python
safety_settings = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
}
```

**Модерация комментариев:**
- Спам/токсичность удаляется в течение 0-6 часов
- AI-классификация без false positives (вручную проверено)

---

## 5. Масштабирование

### 5.1. Текущие лимиты

| Ресурс | Лимит | Текущее использование | Запас |
|--------|-------|-----------------------|-------|
| **SQLite writes** | ~50k/день | ~10 записей/день | 5000x |
| **Telegram API** | 30 msg/сек | <1 msg/мин | 1800x |
| **Gemini API** | 60 req/мин | <1 req/мин | 60x |
| **Serper API** | 2.5k req/мес | 60-100 req/мес | 25x |
| **Disk space** | 10GB (instance) | ~500MB (БД + images) | 20x |

**Вывод:** Архитектура масштабируется на 10x-100x рост без изменений.

---

### 5.2. Bottlenecks (при 100x росте)

**Проблема 1: SQLite concurrent writes**
- Симптом: SQLITE_BUSY errors при >100 записей/сек
- Решение: PostgreSQL migration

**Проблема 2: Telegram rate limits**
- Симптом: TelegramRetryAfter при >30 msg/сек в канал
- Решение: Message queue (Celery + Redis)

**Проблема 3: Gemini rate limits**
- Симптом: HTTP 429 при >60 req/мин
- Решение: Request throttling (aiogram middleware)

**Проблема 4: Single-process scheduler**
- Симптом: Задачи пропускаются при высокой нагрузке
- Решение: Distributed scheduler (Celery Beat)

---

## 6. Мониторинг

### 6.1. Heartbeat System

**Компоненты:**
```
[APScheduler: heartbeat job]
         ↓ каждые 4 часа
[scheduler.py: _job_heartbeat()]
         ↓ пишет в журнал
"HEARTBEAT ok"
         ↓ раз в час
[systemd timer: smoki-heartbeat.timer]
         ↓ запускает
[scripts/heartbeat_healthcheck.sh]
         ↓ проверяет
journalctl -u smoki-bot --since "8 hours ago" | grep "HEARTBEAT ok"
         ↓ если НЕТ
[scripts/notify_admin.sh]
         ↓ алерт
[Telegram: @ADMIN_CHAT_ID]
"🚨 АЛЕРТ: Бот/планировщик завис!"
```

**Параметры:**
- `HEARTBEAT_INTERVAL_HOURS=4` — частота записи
- `HEARTBEAT_MAX_AGE_HOURS=8` — порог тревоги

---

### 6.2. Delivery Watchdog

**Цель:** Детектировать застрявшие статьи (pending/approved не опубликованы).

**Trigger:** `PUBLISH_WINDOW_END + 2 часа` (например, 12:00 MSK)

**Логика:**
```python
async def _job_delivery_watchdog():
    undelivered = await db.get_undelivered_today()
    if undelivered:
        # Алерт админу: "Статьи не доставлены: #123, #124"
```

---

### 6.3. AI Budget Monitoring

**Метрики:**
- `ai_logs` таблица: все вызовы AI с токенами и расходом
- Команда `/stats`: сводка за месяц
- Alert: если расход > `MONTHLY_BUDGET_USD`

**Прогноз:**
```python
days_passed = datetime.now().day
days_in_month = 30
current_spend = sum(ai_logs.est_cost_usd)
projected_spend = current_spend * days_in_month / days_passed

if projected_spend > MONTHLY_BUDGET_USD:
    # Предупреждение админу
```

---

## 7. Disaster Recovery

### 7.1. Backup Strategy

**Автоматический backup:**
- Systemd service: `smoki-backup.service`
- Trigger: ежедневно в 03:00 UTC
- Retention: 30 дней

**Что бэкапится:**
```bash
tar -czf backup_$(date +%Y%m%d).tar.gz \
    data/smoki.db \
    data/images/*.png \
    .env
```

**Хранение:**
- Локально: `/opt/SMOKI/backups/`
- Remote: GCP Storage Bucket (опционально)

---

### 7.2. Recovery Procedures

**Сценарий 1: Потеря БД**
```bash
# 1. Остановить бота
sudo systemctl stop smoki-bot

# 2. Восстановить из backup
cd /opt/SMOKI/bot
tar -xzf /opt/SMOKI/backups/backup_20261012.tar.gz

# 3. Запустить бота
sudo systemctl start smoki-bot
```

**RTO:** <5 минут  
**RPO:** <24 часа (последний дневной backup)

---

**Сценарий 2: Потеря instance (GCP)**
```bash
# 1. Создать новый instance из snapshot
gcloud compute disks create new-disk --source-snapshot=snapshot-20261012

# 2. Attach disk к новому instance
gcloud compute instances attach-disk telegram-bot-new --disk=new-disk

# 3. Start instance
gcloud compute instances start telegram-bot-new
```

**RTO:** <15 минут  
**RPO:** <24 часа (дневной snapshot)

---

## 8. Документация

**См. также:**
- [PRD.md](PRD.md) — продуктовые требования
- [TRD.md](TRD.md) — технические требования
- [FLOW.md](FLOW.md) — пользовательские сценарии
- [DB.md](DB.md) — схема базы данных
- [PLAN.md](PLAN.md) — план внедрения
- [SPEC.md](SPEC.md) — спецификация для разработчиков
- [PROJECT_BOOK.md](PROJECT_BOOK.md) — полная книга проекта

---

**Версия:** 1.0 (13 октября 2026)  
**Контакт:** @shushpanchik_art  
**Лицензия:** Proprietary
