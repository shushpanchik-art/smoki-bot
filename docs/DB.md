# Database Design Document (DB)
## SMOKI-bot — Схема базы данных

**Версия:** 1.0  
**Дата:** 13 октября 2026  
**СУБД:** SQLite 3.x  
**Связанные документы:** [TRD.md](TRD.md), [DESIGN.md](DESIGN.md)

---

## 1. Обзор

### 1.1. Характеристики БД

| Параметр | Значение |
|----------|----------|
| **Тип** | SQLite (embedded) |
| **Файл** | `data/smoki.db` |
| **Размер** | ~50MB (производство, октябрь 2026) |
| **Рост** | ~1GB/год (при 2 поста/день + картинки) |
| **Кодировка** | UTF-8 |
| **Целостность** | FOREIGN KEY constraints включены |

### 1.2. Таблицы

```
┌─────────────────────┐
│  published_topics   │  Темы постов (дедупликация)
└──────────┬──────────┘
           │ 1:N
           v
┌─────────────────────┐
│      articles       │  Статьи (текст + картинка)
└─────────────────────┘

┌─────────────────────┐
│      comments       │  Комментарии из группы
└─────────────────────┘

┌─────────────────────┐
│      ai_logs        │  Логи обращений к AI
└─────────────────────┘

┌─────────────────────┐
│      settings       │  Key-value настройки
└─────────────────────┘

┌─────────────────────┐
│     story_jobs      │  Задания Stories (опционально)
└─────────────────────┘

┌─────────────────────┐
│     saga_state      │  Состояние саги (1 строка)
└─────────────────────┘

┌─────────────────────┐
│   saga_summaries    │  Хроника эпизодов саги
└─────────────────────┘

┌─────────────────────┐
│ apscheduler_jobs    │  APScheduler jobstore (автоматически)
└─────────────────────┘
```

---

## 2. Таблицы (детально)

### 2.1. published_topics

**Назначение:** Хранение тем постов для предотвращения дублей.

**Схема:**
```sql
CREATE TABLE IF NOT EXISTS published_topics (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  topic_hash TEXT UNIQUE,
  category TEXT,
  status TEXT DEFAULT 'draft',
  created_at TEXT DEFAULT (datetime('now'))
);
```

**Поля:**

| Поле | Тип | Описание | Пример |
|------|-----|----------|--------|
| `id` | INTEGER | PK, автоинкремент | 149 |
| `title` | TEXT | Название темы | "Электронные сигареты новости октябрь 2026" |
| `topic_hash` | TEXT | MD5 хеш темы (UNIQUE) | "a3f8d9e2..." |
| `category` | TEXT | Категория (опционально) | "news" |
| `status` | TEXT | Статус темы | "draft" / "published" |
| `created_at` | TEXT | ISO datetime создания | "2026-10-13 08:47:23" |

**Индексы:**
```sql
CREATE INDEX idx_topics_status ON published_topics(status);
CREATE INDEX idx_topics_created_at ON published_topics(created_at);
```

**Связи:**
- `1:N` → `articles.topic_id`

**Правила:**
- `topic_hash` — UNIQUE (защита от дублей тем)
- `status='draft'` — тема создана, статья в модерации
- `status='published'` — статья опубликована

---

### 2.2. articles

**Назначение:** Хранение статей (текст + метаданные картинки).

**Схема:**
```sql
CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY,
  topic_id INTEGER REFERENCES published_topics(id),
  body TEXT NOT NULL,
  image_path TEXT,
  image_prompt TEXT,
  status TEXT DEFAULT 'pending',
  admin_feedback TEXT,
  regen_count INTEGER DEFAULT 0,
  length_hint TEXT,
  message_id INTEGER,
  created_at TEXT DEFAULT (datetime('now')),
  published_at TEXT
);
```

**Поля:**

| Поле | Тип | Описание | Пример |
|------|-----|----------|--------|
| `id` | INTEGER | PK, автоинкремент | 153 |
| `topic_id` | INTEGER | FK → `published_topics.id` | 149 |
| `body` | TEXT | HTML-текст статьи | "<b>Октябрь 2026</b>..." |
| `image_path` | TEXT | Путь к картинке | "data/images/art_1728812843_xyz.png" |
| `image_prompt` | TEXT | Промпт для генерации картинки | "Modern vape device, minimalist..." |
| `status` | TEXT | Статус статьи | "pending" / "approved" / "published" / "rejected" / "cancelled" |
| `admin_feedback` | TEXT | Комментарий админа (при отклонении) | "Слишком длинно" |
| `regen_count` | INTEGER | Число регенераций | 2 |
| `length_hint` | TEXT | Правило длины (использованное) | "facts_rules(3)" |
| `message_id` | INTEGER | ID сообщения в канале (после публикации) | 255 |
| `created_at` | TEXT | ISO datetime создания | "2026-10-13 08:47:23" |
| `published_at` | TEXT | ISO datetime публикации | "2026-10-13 08:52:15" |

**Индексы:**
```sql
CREATE INDEX idx_articles_status ON articles(status);
CREATE INDEX idx_articles_created_at ON articles(created_at);
CREATE INDEX idx_articles_topic_id ON articles(topic_id);
CREATE INDEX idx_articles_message_id ON articles(message_id);
```

**Статусы статьи:**

| Статус | Описание | Переход |
|--------|----------|---------|
| `pending` | На модерации у админа | → `approved`, `rejected`, `cancelled`, `published` |
| `approved` | Одобрена админом, ждёт публикации | → `published` |
| `published` | Опубликована в канале | (финальный) |
| `rejected` | Отклонена админом | (финальный) |
| `cancelled` | Отменена (кнопка ⛔) | (финальный) |

**Правила:**
- `regen_count` инкрементируется при каждой регенерации текста/картинки
- `message_id` заполняется только после публикации
- `published_at` заполняется только при `status='published'`

---

### 2.3. comments

**Назначение:** Комментарии из группы-обсуждения канала для автомодерации.

**Схема:**
```sql
CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY,
  chat_id INTEGER,
  message_id INTEGER,
  user_id INTEGER,
  username TEXT,
  text TEXT,
  status TEXT DEFAULT 'new',
  classification TEXT,
  bot_reply TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  processed_at TEXT,
  UNIQUE(chat_id, message_id)
);
```

**Поля:**

| Поле | Тип | Описание | Пример |
|------|-----|----------|--------|
| `id` | INTEGER | PK, автоинкремент | 42 |
| `chat_id` | INTEGER | Telegram chat_id группы | -1001234567890 |
| `message_id` | INTEGER | ID сообщения в группе | 12345 |
| `user_id` | INTEGER | Telegram user_id автора | 987654321 |
| `username` | TEXT | Username автора (опционально) | "john_doe" |
| `text` | TEXT | Текст комментария | "Какие под-системы лучше?" |
| `status` | TEXT | Статус обработки | "new" / "replied" / "deleted" / "error" |
| `classification` | TEXT | Класс от AI | "reklama" / "toxic" / "question" / "neutral" / "positive" |
| `bot_reply` | TEXT | Ответ бота (если был) | "Для новичков рекомендую..." |
| `created_at` | TEXT | ISO datetime создания | "2026-10-13 10:15:00" |
| `processed_at` | TEXT | ISO datetime обработки | "2026-10-13 16:00:05" |

**Индексы:**
```sql
CREATE INDEX idx_comments_status ON comments(status);
CREATE INDEX idx_comments_processed_at ON comments(processed_at);
CREATE UNIQUE INDEX idx_comments_chat_message ON comments(chat_id, message_id);
```

**Классификация комментариев:**

| Класс | Действие | Пример |
|-------|----------|--------|
| `reklama` | Удаление | "КУПИ ДЕШЕВО +7999..." |
| `toxic` | Удаление | "Вы все идиоты" |
| `question` | AI-ответ | "Какие под-системы лучше?" |
| `neutral` | AI-ответ (если уместно) | "Интересная статья" |
| `positive` | Без ответа | "Спасибо!" |

**Правила:**
- `(chat_id, message_id)` — UNIQUE (один комментарий не сохраняется дважды)
- `status='new'` → обрабатывается scheduler job `process_comments`
- `classification` заполняется AI после обработки

---

### 2.4. ai_logs

**Назначение:** Логирование всех обращений к AI для статистики и бюджета.

**Схема:**
```sql
CREATE TABLE IF NOT EXISTS ai_logs (
  id INTEGER PRIMARY KEY,
  kind TEXT,
  model TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  images INTEGER DEFAULT 0,
  est_cost_usd REAL,
  created_at TEXT DEFAULT (datetime('now'))
);
```

**Поля:**

| Поле | Тип | Описание | Пример |
|------|-----|----------|--------|
| `id` | INTEGER | PK, автоинкремент | 1234 |
| `kind` | TEXT | Тип операции | "text" / "image" / "censor" |
| `model` | TEXT | Модель AI | "gemini-3.1-flash-lite" / "imagen-3-fast" |
| `input_tokens` | INTEGER | Примерное число входных токенов | 1500 |
| `output_tokens` | INTEGER | Примерное число выходных токенов | 800 |
| `images` | INTEGER | Число сгенерированных картинок | 1 |
| `est_cost_usd` | REAL | Оценка расхода (USD) | 0.0012 |
| `created_at` | TEXT | ISO datetime операции | "2026-10-13 08:47:25" |

**Индексы:**
```sql
CREATE INDEX idx_ai_logs_created_at ON ai_logs(created_at);
CREATE INDEX idx_ai_logs_kind ON ai_logs(kind);
```

**Расчёт стоимости:**
```python
# Gemini Flash (текст)
input_cost = (input_tokens / 1_000_000) * PRICE_TEXT_IN_USD_PER_1M
output_cost = (output_tokens / 1_000_000) * PRICE_TEXT_OUT_USD_PER_1M
est_cost_usd = input_cost + output_cost

# Imagen (картинка)
est_cost_usd = images * PRICE_IMAGE_USD
```

**Правила:**
- Токены оцениваются приблизительно (`len(text) / 4`)
- Используется для команды `/stats` (бюджет AI)

---

### 2.5. settings

**Назначение:** Key-value настройки, редактируемые через бота или код.

**Схема:**
```sql
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TEXT DEFAULT (datetime('now'))
);
```

**Поля:**

| Поле | Тип | Описание | Пример |
|------|-----|----------|--------|
| `key` | TEXT | PK, уникальный ключ | "morning_facts" |
| `value` | TEXT | Значение (всегда строка) | "3" |
| `updated_at` | TEXT | ISO datetime обновления | "2026-10-13 12:00:00" |

**Ключи (используемые):**

| Key | Type | Default | Описание | UI |
|-----|------|---------|----------|-----|
| `morning_facts` | int | 2 | Число фактов в утреннем посте (1-3) | `/setlen morning N` |
| `evening_words` | int | 350 | Число слов в вечернем посте (200-500) | `/setlen evening N` |
| `liked_feedback` | text | "" | Накопленные правила "что нравится админу" | Кнопка "💛 Правила нравится" |
| `censor_extra` | text | "" | Накопленные замечания цензуры | Кнопка "🚫 Правила цензуры" |
| `paused_jobs` | csv | "" | Список задач на паузе (id через запятую) | Кнопка "⏸ Пауза утро/вечер" |
| `time_daily_morning` | int | null | Переопределённый час утренней публикации | Кнопка "⏰ Время утро" |
| `time_daily_evening` | int | null | Переопределённый час вечерней публикации | Кнопка "⏰ Время вечер" |

**Правила:**
- Все значения хранятся как TEXT (приведение типов в коде)
- NULL value → используется default из config.py

---

### 2.6. story_jobs

**Назначение:** Задания для автоматических Stories (опциональная фича).

**Схема:**
```sql
CREATE TABLE IF NOT EXISTS story_jobs (
  id INTEGER PRIMARY KEY,
  target TEXT NOT NULL,
  theme INTEGER,
  prompt_en TEXT,
  image_path TEXT,
  caption TEXT,
  status TEXT DEFAULT 'pending',
  feedback TEXT,
  regen_count INTEGER DEFAULT 0,
  message_id INTEGER,
  story_msg_id INTEGER,
  created_at TEXT DEFAULT (datetime('now')),
  publish_at TEXT
);
```

**Поля:**

| Поле | Тип | Описание | Пример |
|------|-----|----------|--------|
| `id` | INTEGER | PK, автоинкремент | 15 |
| `target` | TEXT | Цель публикации | "channel" / "flood" |
| `theme` | INTEGER | Номер темы (1-5) | 3 |
| `prompt_en` | TEXT | EN-промпт для картинки | "Funny vape meme, cartoon style" |
| `image_path` | TEXT | Путь к картинке | "data/images/story_xyz.png" |
| `caption` | TEXT | Подпись к Stories | "😄 Мем дня!" |
| `status` | TEXT | Статус слота | "pending" / "approved" / "published" / "rejected" / "cancelled" / "error" |
| `feedback` | TEXT | Замечание админа (при отклонении) | NULL |
| `regen_count` | INTEGER | Число регенераций | 0 |
| `message_id` | INTEGER | ID сообщения модерации в ЛС админу | 7890 |
| `story_msg_id` | INTEGER | ID опубликованной Stories | 12345 |
| `created_at` | TEXT | ISO datetime создания | "2026-10-13 09:00:00" |
| `publish_at` | TEXT | Время публикации (планируемое) | "2026-10-13 12:00:00" |

**Индексы:**
```sql
CREATE INDEX idx_story_jobs_status ON story_jobs(status);
CREATE INDEX idx_story_jobs_publish_at ON story_jobs(publish_at);
```

**Статус:** Аналогично `articles.status`

**Правила:**
- `message_id` — проставляется при отправке на модерацию (чтобы слот не пере-слался)
- `story_msg_id` — заполняется после публикации

---

### 2.7. saga_state

**Назначение:** Хранение состояния генеративного сериала (Saga). **Одна строка** (id=1).

**Схема:**
```sql
CREATE TABLE IF NOT EXISTS saga_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  episode_number INTEGER DEFAULT 0,
  arc_number INTEGER DEFAULT 1,
  arc_goal TEXT,
  arc_plan_json TEXT DEFAULT '[]',
  planned_arc_length INTEGER DEFAULT 6,
  episode_in_arc INTEGER DEFAULT 0,
  harmon_stage TEXT DEFAULT '1-Ты',
  characters_json TEXT DEFAULT '{}',
  locations_json TEXT DEFAULT '[]',
  last_summary TEXT,
  prev_message_id INTEGER,
  narration TEXT,
  pending_arc_seed TEXT,
  arc_status TEXT DEFAULT 'in_progress',
  arc_synopsis_json TEXT DEFAULT '[]',
  updated_at TEXT DEFAULT (datetime('now'))
);
```

**Поля:**

| Поле | Тип | Описание | Пример |
|------|-----|----------|--------|
| `id` | INTEGER | PK, всегда 1 | 1 |
| `episode_number` | INTEGER | Номер текущего эпизода (глобально) | 42 |
| `arc_number` | INTEGER | Номер текущей арки | 3 |
| `arc_goal` | TEXT | Цель текущей арки | "Найти утраченный рецепт табака" |
| `arc_plan_json` | TEXT | JSON план арки (список эпизодов) | `["Встреча с торговцем", "Путь в горы", ...]` |
| `planned_arc_length` | INTEGER | Планируемая длина арки (эпизодов) | 6 |
| `episode_in_arc` | INTEGER | Номер эпизода внутри арки | 2 |
| `harmon_stage` | TEXT | Стадия Круга Хармона | "3-Иди" / "5-Возьми" |
| `characters_json` | TEXT | JSON персонажи | `{"Владислав": "старый мастер", ...}` |
| `locations_json` | TEXT | JSON локации | `["Лавка табака", "Горы Кавказа"]` |
| `last_summary` | TEXT | Краткое содержание последнего эпизода | "Владислав встретил торговца..." |
| `prev_message_id` | INTEGER | ID последнего сообщения саги в канале | 123456 |
| `narration` | TEXT | Последний хвост текста (связность) | "...и они отправились в путь." |
| `pending_arc_seed` | TEXT | Заготовка следующей арки | NULL |
| `arc_status` | TEXT | Статус арки | "in_progress" / "completed" |
| `arc_synopsis_json` | TEXT | JSON синопсис арки | `["Эп.1: ...", "Эп.2: ..."]` |
| `updated_at` | TEXT | ISO datetime обновления | "2026-10-13 20:00:00" |

**Правила:**
- **Ровно одна строка** (CHECK `id = 1`)
- Обновляется после каждого эпизода саги
- Используется для генерации следующего эпизода

---

### 2.8. saga_summaries

**Назначение:** Хроника всех эпизодов саги (краткое содержание).

**Схема:**
```sql
CREATE TABLE IF NOT EXISTS saga_summaries (
  id INTEGER PRIMARY KEY,
  episode_number INTEGER NOT NULL,
  arc_number INTEGER NOT NULL,
  summary TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);
```

**Поля:**

| Поле | Тип | Описание | Пример |
|------|-----|----------|--------|
| `id` | INTEGER | PK, автоинкремент | 42 |
| `episode_number` | INTEGER | Номер эпизода (глобально) | 42 |
| `arc_number` | INTEGER | Номер арки | 3 |
| `summary` | TEXT | Краткое содержание эпизода | "Владислав встретил торговца табаком..." |
| `created_at` | TEXT | ISO datetime создания | "2026-10-13 20:00:00" |

**Индексы:**
```sql
CREATE INDEX idx_saga_summaries_episode ON saga_summaries(episode_number);
CREATE INDEX idx_saga_summaries_arc ON saga_summaries(arc_number);
```

**Правила:**
- Одна запись на эпизод
- Используется для "Previous on..." промпта

---

### 2.9. apscheduler_jobs

**Назначение:** Служебная таблица APScheduler (persistent jobstore).

**Схема:** Создаётся автоматически APScheduler.

**Поля:**
- `id` — job ID (строка)
- `next_run_time` — следующий запуск (timestamp)
- `job_state` — сериализованный state (blob)

**Правила:**
- Не редактируется вручную
- Используется scheduler.py

---

## 3. Миграции

### 3.1. Начальная схема

**Файл:** `db/schema.sql`  
**Применение:** При первом запуске (`init_db()`)

**Метод:**
```python
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        with open("db/schema.sql") as f:
            await db.executescript(f.read())
        await db.commit()
```

---

### 3.2. Миграция: saga_posts

**Когда:** При первом обращении к Saga (если таблица не существует)

**Код:** `db/database.py:_migrate_saga()`

**Таблица:**
```sql
CREATE TABLE IF NOT EXISTS saga_posts (
  id INTEGER PRIMARY KEY,
  episode_number INTEGER NOT NULL,
  part_number INTEGER NOT NULL,
  message_id INTEGER NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);
```

**Назначение:** Журнал message_id частей каждого эпизода саги (контроль, что посты живы в канале).

---

### 3.3. Миграция: story_jobs.message_id

**Когда:** При первом обращении к Stories (если колонка не существует)

**Код:** `db/database.py:_migrate_story_jobs()`

**Изменение:**
```sql
ALTER TABLE story_jobs ADD COLUMN message_id INTEGER;
```

**Назначение:** Хранение ID сообщения модерации в ЛС админу (чтобы слот не пере-слался повторно).

---

## 4. Индексы

### 4.1. Производственные индексы

```sql
-- Topics
CREATE INDEX idx_topics_status ON published_topics(status);
CREATE INDEX idx_topics_created_at ON published_topics(created_at);

-- Articles
CREATE INDEX idx_articles_status ON articles(status);
CREATE INDEX idx_articles_created_at ON articles(created_at);
CREATE INDEX idx_articles_topic_id ON articles(topic_id);
CREATE INDEX idx_articles_message_id ON articles(message_id);

-- Comments
CREATE INDEX idx_comments_status ON comments(status);
CREATE INDEX idx_comments_processed_at ON comments(processed_at);
CREATE UNIQUE INDEX idx_comments_chat_message ON comments(chat_id, message_id);

-- AI Logs
CREATE INDEX idx_ai_logs_created_at ON ai_logs(created_at);
CREATE INDEX idx_ai_logs_kind ON ai_logs(kind);

-- Story Jobs
CREATE INDEX idx_story_jobs_status ON story_jobs(status);
CREATE INDEX idx_story_jobs_publish_at ON story_jobs(publish_at);

-- Saga Summaries
CREATE INDEX idx_saga_summaries_episode ON saga_summaries(episode_number);
CREATE INDEX idx_saga_summaries_arc ON saga_summaries(arc_number);
```

**Обоснование:**
- `status` — частые фильтры в WHERE
- `created_at` — сортировка/фильтрация по дате
- `(chat_id, message_id)` — UNIQUE constraint для комментариев

---

## 5. Запросы (примеры)

### 5.1. Получить статьи на модерации сегодня

```sql
SELECT a.id, a.body, a.image_path, t.title
FROM articles a
JOIN published_topics t ON a.topic_id = t.id
WHERE a.status IN ('pending', 'approved')
  AND DATE(a.created_at) = DATE('now')
ORDER BY a.created_at ASC;
```

---

### 5.2. Получить новые комментарии для обработки

```sql
SELECT id, chat_id, message_id, user_id, username, text
FROM comments
WHERE status = 'new'
ORDER BY created_at ASC
LIMIT 50;
```

---

### 5.3. Статистика AI за текущий месяц

```sql
SELECT 
  kind,
  COUNT(*) as calls,
  SUM(input_tokens) as total_input,
  SUM(output_tokens) as total_output,
  SUM(images) as total_images,
  SUM(est_cost_usd) as total_cost
FROM ai_logs
WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
GROUP BY kind;
```

---

### 5.4. Последние 200 тем (для дедупликации)

```sql
SELECT title
FROM published_topics
WHERE status = 'published'
ORDER BY created_at DESC
LIMIT 200;
```

---

## 6. Backup & Recovery

### 6.1. Полный backup

```bash
# Остановить бота (для целостности)
sudo systemctl stop smoki-bot

# Backup БД + картинки
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    data/smoki.db \
    data/images/

# Запустить бота
sudo systemctl start smoki-bot
```

---

### 6.2. Recovery из backup

```bash
# Остановить бота
sudo systemctl stop smoki-bot

# Восстановить
cd /opt/SMOKI/bot
tar -xzf /backups/backup_20261012_030000.tar.gz

# Запустить бота
sudo systemctl start smoki-bot
```

---

### 6.3. Point-in-time recovery (SQLite)

**SQLite не поддерживает PITR** (в отличие от PostgreSQL).

**Альтернатива:** Ежедневные backups (retention 30 дней).

**RPO:** <24 часа

---

## 7. Оптимизация

### 7.1. VACUUM (дефрагментация)

**Когда:** Ежемесячно (или при росте >2x от фактического размера)

```sql
VACUUM;
```

**Эффект:** Уменьшение размера файла БД на 20-30%.

---

### 7.2. ANALYZE (статистика)

**Когда:** После массовых операций (например, импорт 1000+ записей)

```sql
ANALYZE;
```

**Эффект:** Обновление статистики для оптимизатора запросов.

---

### 7.3. WAL mode (Write-Ahead Logging)

**Статус:** Не включен (default: DELETE journal_mode)

**Преимущества WAL:**
- Concurrent reads during writes
- Меньше fsync операций

**Недостатки:**
- 3 файла вместо 1 (`smoki.db`, `smoki.db-wal`, `smoki.db-shm`)
- Сложнее backup

**Вывод:** DELETE mode достаточно для текущей нагрузки (<10 записей/мин).

---

## 8. Ограничения SQLite

### 8.1. Известные лимиты

| Лимит | Значение | Текущее использование |
|-------|----------|----------------------|
| **Max DB size** | 281 TB | ~50MB (0.00002%) |
| **Max row count** | 2^64 | ~10k (0.0000000001%) |
| **Max table count** | ~1M | 9 таблиц |
| **Max columns** | 2000 | Max 17 (saga_state) |
| **Max SQL length** | 1M chars | Max ~10k (промпты) |

**Вывод:** Лимиты SQLite не будут достигнуты в ближайшие 100 лет.

---

### 8.2. Concurrent writes

**Проблема:** SQLite блокирует всю БД при write.

**Решение (текущее):** Sequential writes (один процесс, asyncio queue).

**Когда станет проблемой:** При >100 записей/сек (сейчас <1/сек).

**Миграция на PostgreSQL:** При 100x росте нагрузки.

---

## 9. Документация

**См. также:**
- [TRD.md](TRD.md) — технические требования
- [DESIGN.md](DESIGN.md) — архитектура системы
- [SPEC.md](SPEC.md) — спецификация для разработчиков
- [PROJECT_BOOK.md](PROJECT_BOOK.md) — полная книга проекта

---

**Версия:** 1.0 (13 октября 2026)  
**Контакт:** @shushpanchik_art  
**Лицензия:** Proprietary
