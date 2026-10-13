# Technical Requirements Document (TRD)
## SMOKI-bot — Technical Specifications

**Версия:** 1.0  
**Дата:** 13 октября 2026  
**Связанные документы:** [PRD.md](PRD.md), [DESIGN.md](DESIGN.md), [DB.md](DB.md)

---

## 1. Архитектурный стек

### 1.1. Языки и runtime

| Компонент | Технология | Версия | Обоснование |
|-----------|-----------|--------|-------------|
| **Backend** | Python | 3.11+ | Async/await, rich ecosystem, быстрая разработка |
| **Database** | SQLite | 3.x | Embedded, zero-config, достаточно для <10k записей/день |
| **Bot Framework** | aiogram | 3.x | Modern async Telegram bot framework |
| **Scheduler** | APScheduler | 3.x | Persistent jobstore, misfire handling |

### 1.2. Внешние API

| Сервис | Назначение | SLA | Fallback |
|--------|-----------|-----|----------|
| **Telegram Bot API** | Публикация постов, модерация | 99.9% | Retry + alert |
| **Google Gemini (Vertex AI)** | Генерация текста | 99.5% | AI Studio key |
| **Google Gemini (Imagen)** | Генерация картинок | 99.5% | Imagen 3 Fast |
| **Serper News API** | Поиск новостей | 99% | Google grounding |
| **GCP Infrastructure** | Compute Engine, IAM | 99.95% | Manual intervention |

### 1.3. Инфраструктура

```
GCP Compute Engine (us-central1-c)
├── Instance: telegram-bot
│   ├── OS: Debian 12 (Bookworm)
│   ├── Python: 3.11.2
│   ├── Process manager: systemd
│   └── Service: smoki-bot.service
├── Service Account: smoki-bot-vertex-sa@project-xxx.iam.gserviceaccount.com
│   ├── Role: Vertex AI User
│   └── Workload Identity для Gemini API
└── Backup: daily snapshot (retention 30 days)
```

---

## 2. Функциональные требования

### 2.1. Генерация контента

#### R-GEN-001: Hybrid News Search
**Приоритет:** P1 (важно)  
**Статус:** ✅ Implemented (13 окт. 2026)

**Требование:**  
Система должна определять новостные темы по ключевым словам (`новост*`, `событи*`, `заявил*`, `объявил*`, `запрет*`, `закон*`) и использовать Serper News API для получения актуальных новостей (последние 7 дней).

**Технические детали:**
- Модуль: `ai/search.py`
- API endpoint: `https://google.serper.dev/news`
- Параметры: `q` (query), `num` (5), `tbs` (qdr:d7), `gl=ru`, `hl=ru`
- Timeout: 10 секунд
- Fallback: Google Search grounding (встроенный в Gemini)

**Acceptance criteria:**
- ✅ Новостные темы используют Serper API
- ✅ Не-новостные темы используют Google grounding
- ✅ При отсутствии `SERPER_API_KEY` → fallback на grounding
- ✅ При HTTP 500 от Serper → fallback на grounding
- ✅ Извлечение `imageUrl` из результатов (для F-IMG-002)

---

#### R-GEN-002: Утренний пост (Facts + Joke)
**Приоритет:** P0 (критично)

**Требование:**  
Генерация короткого утреннего поста (08:00-10:00 MSK) по формату:
- 100-150 слов (строго)
- 1-3 факта (настраивается через `/setlen morning N`)
- Обязательная короткая шутка в конце
- Позитивный тон, без агрессии

**Технические детали:**
- Функция: `prompts.facts_rules(n)` → length_hint
- Параметр: `length_hint=prompts.facts_rules(n)` в `generate_article()`
- Модель: Gemini Flash 3.1 (быстро + дешево)

**Acceptance criteria:**
- ✅ Длина 100-150 слов (проверка в тестах)
- ✅ Наличие шутки в конце (автоцензура проверяет тон)
- ✅ N фактов соответствует настройке `morning_facts` из БД

---

#### R-GEN-003: Вечерний лонг-рид
**Приоритет:** P0 (критично)

**Требование:**  
Генерация развёрнутой статьи (19:00-20:00 MSK):
- 200-500 слов (настраивается через `/setlen evening N`)
- Глубокая проработка темы
- Возможность Saga-эпизода (если `SAGA_ENABLED=1`, вес 0.7)

**Технические детали:**
- Функция: `prompts.words_rule(w)` → length_hint
- Saga: вероятность = `SAGA_RATIO` (default 0.7) при `SAGA_ENABLED=1`
- Saga-эпизод: 600-1000 слов, публикуется reply-цепочкой без модерации

**Acceptance criteria:**
- ✅ Длина 200-500 слов (или 600-1000 для Saga)
- ✅ Saga включается только при `SAGA_ENABLED=1`
- ✅ Saga публикуется без модерации

---

#### R-GEN-004: Автоцензура
**Приоритет:** P0 (критично)

**Требование:**  
Все статьи перед публикацией проходят автоматическую проверку на нарушение правил:

**Запрещено:**
- ❌ Призыв к покупке и курению
- ❌ Медицинские советы
- ❌ Утверждения о пользе курения
- ❌ Агрессивный тон
- ❌ Утверждения без источников (для новостей)

**Разрешено:**
- ✅ Нейтральное упоминание брендов
- ✅ Образовательный контент
- ✅ Исторические факты

**Технические детали:**
- Функция: `services.censor.censor(text)` → `(bool, str)`
- Модель: Gemini Flash (без search)
- Поведение при нарушении:
  - Первая попытка: автоматическая регенерация (до 3 раз)
  - После 3 неудач: статья отменяется, админ получает alert

**Acceptance criteria:**
- ✅ 100% статей проходят проверку перед публикацией
- ✅ Нарушения логируются в `ai_logs` (kind='censor')
- ✅ Успешность >95% (метрика из PRD)

---

### 2.2. Генерация изображений

#### R-IMG-001: AI-генерация картинок
**Приоритет:** P0 (критично)

**Требование:**  
Для каждой статьи генерируется иллюстрация 4:5 (портретная ориентация, оптимизация под Instagram).

**Технические детали:**
- Модель: Imagen 3 Fast (Google Vertex AI)
- Формат: PNG, aspect ratio 4:5 (вертикальная)
- Промпт: генерируется AI на основе текста статьи
- Хранение: `data/images/<timestamp>.png`
- Safety filter: block `HARM_CATEGORY_DANGEROUS_CONTENT`

**Acceptance criteria:**
- ✅ Картинка генерируется для каждого поста
- ✅ Aspect ratio 4:5 (не квадрат!)
- ✅ Safety filter включен
- ✅ Админ видит картинку в черновике перед публикацией

---

#### R-IMG-002: Картинки из новостей (imageUrl)
**Приоритет:** P1 (важно)  
**Статус:** ✅ Implemented (13 окт. 2026)

**Требование:**  
При генерации новостной статьи через Serper API использовать поле `imageUrl` для публикации картинки из источника новости вместо AI-генерации.

**Технические детали:**
- Поле: `NewsItem.imageUrl` (строка, может быть пустой)
- Публикация: через `URLInputFile` (aiogram) без скачивания
- Fallback: если `imageUrl` пустой → AI-генерация

**Acceptance criteria:**
- ✅ `imageUrl` извлекается из Serper response
- ✅ Если `imageUrl` непустой → публикуется через URLInputFile
- ✅ Если `imageUrl` пустой или битая ссылка → AI-генерация

---

### 2.3. Модерация

#### R-MOD-001: Черновик с кнопками
**Приоритет:** P0 (критично)

**Требование:**  
Каждый сгенерированный пост отправляется администратору в ЛС с 5 кнопками управления:

| Кнопка | Действие | Статус статьи |
|--------|---------|---------------|
| ✅ Опубликовать | Публикация в канал | `approved` → `published` |
| 🔄 Регенерировать текст | Новая генерация текста | `pending` |
| 🖼 Регенерировать картинку | Новая генерация картинки | `pending` |
| 📝 Редактировать | (Заглушка: "Пока недоступно") | без изменений |
| ⛔ Отмена | Отмена публикации | `cancelled` |

**Технические детали:**
- Handler: `handlers/moderation.py`
- Inline keyboard: `InlineKeyboardMarkup` с 5 кнопками
- Callback data: `approve_{article_id}`, `regen_text_{id}`, `regen_image_{id}`, `edit_{id}`, `cancel_{id}`
- Message format: картинка + caption с текстом поста

**Acceptance criteria:**
- ✅ Черновик отправляется админу в течение 5 секунд после генерации
- ✅ Все 5 кнопок работают
- ✅ Регенерация текста сохраняет картинку
- ✅ Регенерация картинки сохраняет текст

---

#### R-MOD-002: Автопубликация по дедлайну
**Приоритет:** P0 (критично)

**Требование:**  
Если администратор не промодерировал черновики до дедлайна, бот публикует их автоматически:

**Дедлайны:**
- Утренний пост: `PUBLISH_WINDOW_END` (default: 10:00 MSK)
- Вечерний пост: `EVENING_DEADLINE_HOUR:EVENING_DEADLINE_MINUTE` (default: 20:30 MSK)

**Поведение:**
1. За `PREVIEW_WARN_MINUTES` минут (default: 15) до дедлайна → предупреждение админу
2. В момент дедлайна:
   - Все статьи со статусом `pending` или `approved` за сегодня → автопубликация
   - Админу отправляется сводка: "Опубликовано автоматически: #123, #124"

**Технические детали:**
- Scheduler jobs: `publish_deadline`, `publish_deadline_evening`
- Функция: `scheduler._job_deadline()`
- Preview: `scheduler._job_preview_warn()`

**Acceptance criteria:**
- ✅ Предупреждение приходит за 15 минут
- ✅ Автопубликация срабатывает точно в дедлайн
- ✅ Админ получает сводку после автопубликации

---

### 2.4. Публикация

#### R-PUB-001: Умная разбивка длинных текстов
**Приоритет:** P0 (критично)

**Требование:**  
Telegram ограничивает:
- Caption (подпись к картинке): 1024 символа
- Текстовое сообщение: 4096 символов

**Логика разбивки:**
1. Если `len(text) ≤ 1024` → публикуется как caption к картинке
2. Если `1024 < len(text) ≤ 4096` → картинка отдельно, текст отдельно
3. Если `len(text) > 4096` → разбивка на N сообщений (не должно происходить при корректной генерации)

**Технические детали:**
- Функция: `services.publisher.publish_article(article_id)`
- Метод: `bot.send_photo()` с `caption` или `bot.send_message()` после фото

**Acceptance criteria:**
- ✅ Короткие посты (≤1024) публикуются как caption
- ✅ Длинные посты разбиваются корректно
- ✅ HTML-разметка сохраняется при разбивке

---

#### R-PUB-002: HTML-разметка
**Приоритет:** P1 (важно)

**Требование:**  
Поддержка HTML-форматирования в постах:
- `<b>жирный</b>`
- `<i>курсив</i>`
- `<a href="...">ссылка</a>`
- `<code>код</code>`

**Технические детали:**
- Parse mode: `ParseMode.HTML`
- Очистка: `services.content._clean_html()` удаляет опасные теги

**Acceptance criteria:**
- ✅ Gemini генерирует текст с HTML-тегами
- ✅ Telegram корректно отображает форматирование
- ✅ Опасные теги (`<script>`, `<iframe>`) удаляются

---

### 2.5. Модерация комментариев

#### R-COM-001: Автоматическая классификация
**Приоритет:** P1 (важно)

**Требование:**  
Каждые `COMMENTS_INTERVAL_HOURS` часов (default: 6) бот обрабатывает новые комментарии из группы-обсуждения канала:

**Классы:**
- `reklama` → удаление без ответа
- `toxic` → удаление без ответа
- `question` → AI-ответ
- `neutral` → AI-ответ (если уместно)
- `positive` → без ответа (позитив не требует реакции)

**Технические детали:**
- Модуль: `services/comments_moderator.py`
- Модель: Gemini Flash (без search)
- Функция: `process_new_comments()` → вызывается scheduler
- Хранение: таблица `comments` (БД)

**Acceptance criteria:**
- ✅ Спам удаляется в течение `COMMENTS_INTERVAL_HOURS`
- ✅ Вопросы получают ответы
- ✅ Токсичность удаляется
- ✅ Логирование всех действий в БД

---

## 3. Нефункциональные требования

### 3.1. Производительность

| Метрика | Требование | Текущее значение |
|---------|-----------|------------------|
| **Генерация статьи** | <10 сек | ✅ 4.6 сек |
| **Генерация картинки** | <30 сек | ✅ 8-12 сек |
| **Автоцензура** | <3 сек | ✅ 0.7-1.2 сек |
| **Публикация в канал** | <5 сек | ✅ 1-2 сек |
| **Обработка комментария** | <5 сек | ✅ 2-3 сек |

### 3.2. Надёжность

| Требование | SLA | Реализация |
|-----------|-----|------------|
| **Uptime бота** | 99% | systemd auto-restart + heartbeat monitoring |
| **Доставка постов** | 100% | Автопубликация по дедлайну |
| **Backup БД** | Ежедневно | GCP snapshot, retention 30 дней |
| **Fallback AI** | <1 мин | AI Studio key при недоступности Vertex |

### 3.3. Масштабируемость

**Текущая нагрузка:**
- 2 поста/день → ~60 генераций/месяц
- 3-12 Stories/день → ~150 генераций/месяц (если включены)
- 10-50 комментариев/неделю → ~200 обработок/месяц

**Лимиты:**
- SQLite: до 1M записей (текущие ~10k/год → запас 100 лет)
- Serper API: 2,500 запросов/мес (текущие 60-100 → запас 25x)
- Gemini: rate limit 60 req/min (текущие <1 req/min)

**Вывод:** Архитектура масштабируется на 10x-100x рост без изменений.

### 3.4. Безопасность

#### SEC-001: API Keys
- ✅ Все ключи в `.env` (не в коде)
- ✅ `.env` в `.gitignore`
- ✅ Права на `.env`: 600 (только владелец читает)

#### SEC-002: Service Account
- ✅ Workload Identity для Vertex AI (без JSON-ключей)
- ✅ Минимальные права: `roles/aiplatform.user`

#### SEC-003: Content Safety
- ✅ Автоцензура перед публикацией
- ✅ Imagen safety filter (dangerous content blocked)
- ✅ Модерация комментариев (удаление спама/токсичности)

### 3.5. Мониторинг

#### MON-001: Heartbeat
**Компоненты:**
1. Scheduler job: пишет "HEARTBEAT ok" каждые 4 часа
2. Systemd timer: проверяет журнал каждый час
3. Alert: если нет heartbeat >8 часов → Telegram alert админу

**Файлы:**
- `scheduler.py:heartbeat()`
- `scripts/heartbeat_healthcheck.sh`
- `smoki-heartbeat.timer` (systemd)

#### MON-002: AI Logs
Все обращения к AI логируются в таблицу `ai_logs`:
- `kind`: text/image/censor
- `model`: gemini-flash/imagen-3-fast
- `input_tokens`, `output_tokens`, `images`
- `est_cost_usd`: оценка расхода

**Статистика:**
- Команда: `/stats` → расход за текущий месяц
- Budget alert: при превышении `MONTHLY_BUDGET_USD`

---

## 4. Интеграции

### 4.1. Telegram Bot API

**Endpoints:**
- `sendMessage` — текстовые сообщения
- `sendPhoto` — картинка + caption
- `deleteMessage` — удаление комментариев
- `editMessageReplyMarkup` — обновление кнопок

**Rate limits:**
- 30 сообщений/секунду в канал
- Unlimited в личку админу

**Retry logic:**
- `SEND_RETRIES=3` (config)
- `SEND_RETRY_DELAY=5` секунд между попытками

### 4.2. Google Vertex AI (Gemini)

**Models:**
- `gemini-3.1-flash-lite` — генерация текста (primary)
- `gemini-1.5-flash-002` — fallback model
- `imagen-3.0-generate-001` → `imagen-3.0-fast-generate-001` — генерация картинок

**Authentication:**
- Primary: Workload Identity (service account)
- Fallback: AI Studio API key (env `GOOGLE_AI_STUDIO_KEY`)

**Features:**
- Google Search grounding (`use_search=True`)
- Safety settings (medium threshold)
- JSON mode (structured output)

### 4.3. Serper News API

**Endpoint:** `https://google.serper.dev/news`

**Request:**
```json
{
  "q": "query",
  "num": 5,
  "tbs": "qdr:d7",
  "gl": "ru",
  "hl": "ru"
}
```

**Response fields:**
- `title`, `snippet`, `source`, `date`, `link`
- `imageUrl` (опционально) — URL картинки новости

**Rate limits:**
- Free tier: 2,500 запросов/месяц
- Текущая нагрузка: 60-100/месяц

---

## 5. Конфигурация

### 5.1. Environment Variables

**Критичные (обязательны):**
```bash
# Telegram
BOT_TOKEN=<bot-token>
ADMIN_ID=<telegram-user-id>
CHANNEL_ID=<channel-id>

# Google AI
GOOGLE_AI_PROJECT=project-xxx
GOOGLE_AI_LOCATION=global
```

**Опциональные (есть defaults):**
```bash
# Serper API (fallback на Google grounding)
SERPER_API_KEY=

# AI Studio fallback
GOOGLE_AI_STUDIO_KEY=

# Scheduling
MORNING_START=8
EVENING_START=19
PUBLISH_WINDOW_END=10
```

См. полный список в `.env.example` (51 переменная).

### 5.2. Database Settings

Редактируемые настройки (таблица `settings`):

| Key | Type | Default | UI |
|-----|------|---------|-----|
| `morning_facts` | int | 2 | `/setlen morning N` |
| `evening_words` | int | 350 | `/setlen evening N` |
| `time_daily_morning` | int | null | Кнопка "⏰ Время утро" |
| `time_daily_evening` | int | null | Кнопка "⏰ Время вечер" |
| `paused_jobs` | CSV | "" | Кнопки "⏸ Пауза утро/вечер" |

---

## 6. Deployment

### 6.1. Server Requirements

**Минимальные:**
- OS: Debian 12 (Bookworm) или новее
- Python: 3.11+
- RAM: 512MB (реально используется ~200MB)
- Disk: 2GB (БД + картинки растут ~1GB/год)
- CPU: 1 vCPU (нагрузка <5%)

**Рекомендуемые (production):**
- GCP e2-micro instance (0.25-2 vCPU, 1GB RAM)
- Стоимость: ~$7/месяц

### 6.2. Installation Steps

```bash
# 1. Clone repo
git clone <repo-url> /opt/SMOKI/bot
cd /opt/SMOKI/bot

# 2. Python venv
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Отредактировать .env: BOT_TOKEN, ADMIN_ID, CHANNEL_ID, etc.

# 4. Initialize DB
venv/bin/python -c "from db.database import init_db; import asyncio; asyncio.run(init_db())"

# 5. Systemd service
sudo cp systemd/smoki-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable smoki-bot
sudo systemctl start smoki-bot

# 6. Heartbeat monitor
sudo cp systemd/smoki-heartbeat.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable smoki-heartbeat.timer
sudo systemctl start smoki-heartbeat.timer

# 7. Verify
journalctl -u smoki-bot -f
```

### 6.3. CI/CD

**GitHub Actions** (`.github/workflows/ci.yml`):
- Lint: `ruff check`
- Type check: `mypy`
- Tests: `pytest --cov --cov-fail-under=45`
- Security: `bandit -r .`

**Jobs:** 10 параллельных проверок

**Deployment:** Manual (SSH + git pull + systemctl restart)

---

## 7. Testing

### 7.1. Unit Tests

**Coverage:** ≥45% (requirement)

**Modules:**
- `tests/test_content.py` — генерация контента
- `tests/test_censor.py` — автоцензура
- `tests/test_search.py` — Serper API
- `tests/test_comments.py` — модерация комментариев
- `tests/test_env_example.py` — валидация config

**Mocking:**
- Все API вызовы мокируются (`MagicMock`, `AsyncMock`)
- Нет реальных HTTP запросов в тестах
- БД: in-memory SQLite (`:memory:`)

### 7.2. Integration Tests

**Smoke tests** (`docs/SMOKE_TESTS.md`):
1. Генерация утреннего поста
2. Генерация вечернего поста
3. Модерация комментария
4. Публикация в канал
5. Heartbeat check

**Запуск:**
```bash
# Локально (с мокированным Telegram)
pytest tests/test_smoke.py -v

# На проде (реальный канал)
# См. docs/SMOKE_TESTS.md
```

---

## 8. Обслуживание

### 8.1. Мониторинг

**Ежедневно:**
- ✅ Heartbeat OK (автоматическая проверка)
- ✅ 2 поста опубликовано (админ видит в канале)

**Еженедельно:**
- Проверка логов: `journalctl -u smoki-bot --since "7 days ago" | grep ERROR`
- Размер БД: `ls -lh data/smoki.db` (норма: <100MB)

**Ежемесячно:**
- AI budget: команда `/stats` в боте
- Backup check: GCP Console → Snapshots

### 8.2. Backup & Restore

**Автоматический backup:**
- GCP snapshots: ежедневно в 03:00 UTC
- Retention: 30 дней
- Restore: из GCP Console или `gcloud compute disks create`

**Ручной backup:**
```bash
# БД + картинки
tar -czf backup_$(date +%Y%m%d).tar.gz data/
scp backup_*.tar.gz user@backup-server:/backups/
```

### 8.3. Troubleshooting

**Проблема:** Бот не отвечает

```bash
# 1. Проверка процесса
sudo systemctl status smoki-bot

# 2. Логи
journalctl -u smoki-bot -n 100 --no-pager

# 3. Перезапуск
sudo systemctl restart smoki-bot
```

**Проблема:** Задачи планировщика не выполняются

```bash
# 1. Проверка heartbeat
journalctl -u smoki-bot | grep HEARTBEAT | tail -5

# 2. Проверка jobstore
sqlite3 data/smoki.db "SELECT * FROM apscheduler_jobs;"

# 3. Restart + force run
sudo systemctl restart smoki-bot
# Утренний пост вручную: /generate_morning в боте
```

---

## 9. Constraints & Limitations

### 9.1. Технические ограничения

| Ограничение | Причина | Обход |
|-------------|---------|-------|
| **SQLite (single process)** | Нет concurrent writes | Достаточно для 2 поста/день |
| **No edit in bot** | Сложная UI логика | Админ редактирует вручную после публикации |
| **Imagen 4:5 only** | Ограничение API | Нет обхода |
| **Serper free tier (2.5k/мес)** | Бюджет | Fallback на grounding |

### 9.2. Известные проблемы

**ISSUE-001:** Длинные новостные посты без imageUrl  
**Статус:** Won't fix (редко, <5% случаев)  
**Workaround:** AI-генерация картинки

**ISSUE-002:** Saga иногда теряет контекст между эпизодами  
**Статус:** Known limitation (LLM context window)  
**Workaround:** Ручная корректировка `saga_state.recap`

---

## 10. Roadmap

### Q4 2026
- [ ] Webhook вместо polling (снижение latency)
- [ ] A/B тест: Serper vs Google grounding (качество новостей)
- [ ] Prometheus metrics экспорт

### Q1 2027
- [ ] Мультиязычность (английский канал)
- [ ] Telegram Mini App (аналитика для админа)
- [ ] Auto-download imageUrl для офлайн-хранения

---

## Документация

**См. также:**
- [PRD.md](PRD.md) — продуктовые требования
- [FLOW.md](FLOW.md) — пользовательские сценарии
- [DESIGN.md](DESIGN.md) — архитектура системы
- [DB.md](DB.md) — схема базы данных
- [SPEC.md](SPEC.md) — спецификация для разработчиков
- [PROJECT_BOOK.md](PROJECT_BOOK.md) — полная книга проекта

---

**Версия:** 1.0 (13 октября 2026)  
**Контакт:** @shushpanchik_art  
**Лицензия:** Proprietary
