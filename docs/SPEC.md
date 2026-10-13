# SMOKI-bot — Спецификация для разработчиков

**Версия:** 2.0  
**Дата:** 13 октября 2026  
**Цель:** Практическое руководство для разработки, деплоя и отладки

---

## Быстрый старт

**См. подробную документацию:**
- [PRD.md](PRD.md) — что делает продукт и зачем
- [TRD.md](TRD.md) — технические требования
- [FLOW.md](FLOW.md) — пользовательские сценарии
- [DESIGN.md](DESIGN.md) — архитектура системы
- [DB.md](DB.md) — схема базы данных
- [PLAN.md](PLAN.md) — roadmap и план развития
- [PROJECT_BOOK.md](PROJECT_BOOK.md) — полная книга проекта

---

## 1. Инфраструктура

### 1.1. Production Environment

**Сервер:** `telegram-bot` (GCP Compute Engine, Debian 12)  
**Расположение:** us-central1-c  
**Проект:** `project-dfb3fb77-77cb-4e79-bbb`

**Пути:**
- Код: `/opt/SMOKI/bot`
- Venv: `/opt/SMOKI/bot/venv`
- БД: `/opt/SMOKI/bot/data/smoki.db`
- Картинки: `/opt/SMOKI/bot/data/images/`
- Логи: `journalctl -u smoki-bot`

**Systemd service:**
```bash
sudo systemctl status smoki-bot
sudo systemctl restart smoki-bot
journalctl -u smoki-bot -n 50 --no-pager
```

**Systemd timers:**
- `smoki-backup.timer` — ежедневный backup БД + images
- `smoki-heartbeat.timer` — проверка живости бота (каждый час)
- `smoki-backup-summary.timer` — ежедневная сводка бэкапов (23:45 MSK)

**GitHub Actions:** Self-hosted runner на сервере (`actions.runner.shushpanchik-art-smoki-bot.smoki-agent.service`)

---

### 1.2. Stack

| Компонент | Версия |
|-----------|--------|
| Python | 3.11.2 |
| aiogram | 3.30.0 |
| aiosqlite | 0.22.1 |
| APScheduler | 3.11.3 |
| SQLAlchemy | 2.0.52 |
| google-genai | 2.19.0 |
| aiohttp | 3.11.11 |
| Pillow | 12.3.0 |
| Telethon | 1.44.0 (userbot для Stories) |

**См. полный список:** `requirements.txt`

---

## 2. Доступ к серверу

### 2.1. SSH для человека

```bash
# Метод 1: Прямой SSH (если настроен ключ)
ssh artemijvisnevskij@<SERVER_HOST>

# Метод 2: Через gcloud (всегда работает)
gcloud compute ssh telegram-bot --project=project-dfb3fb77-77cb-4e79-bbb --zone=us-central1-c
```

**Пользователи:**
- `artemijvisnevskij` — рабочий пользователь (sudo access)
- `shushpanchik_art` — владелец файлов проекта (без прямого SSH)

**Работа с проектом:**
```bash
# Switch to project owner
sudo -u shushpanchik_art -s
cd /opt/SMOKI/bot
source venv/bin/activate
```

---

### 2.2. SSH для AI (Claude Code)

**Проблема:** Прямой SSH через IP не работает. Алиасы из `~/.zshrc` недоступны AI.

**Решение:** Всегда использовать `gcloud compute ssh` с полными параметрами.

**Шаблон команды:**
```bash
gcloud compute ssh telegram-bot --zone=us-central1-c --project=project-dfb3fb77-77cb-4e79-bbb --command="КОМАНДА"
```

**Работа от имени shushpanchik_art:**
```bash
gcloud compute ssh telegram-bot --zone=us-central1-c --project=project-dfb3fb77-77cb-4e79-bbb \
  --command="sudo -u shushpanchik_art bash -c 'cd /opt/SMOKI/bot && source venv/bin/activate && КОМАНДА'"
```

**Примеры:**

```bash
# 1. Проверка конфигурации
gcloud compute ssh telegram-bot --zone=us-central1-c --project=project-dfb3fb77-77cb-4e79-bbb \
  --command="sudo -u shushpanchik_art bash -c 'cd /opt/SMOKI/bot && source venv/bin/activate && python3 -c \"import config; print(config.CHANNEL_ID)\"'"

# 2. Многострочный Python (heredoc)
gcloud compute ssh telegram-bot --zone=us-central1-c --project=project-dfb3fb77-77cb-4e79-bbb \
  --command="sudo -u shushpanchik_art bash -c 'cd /opt/SMOKI/bot && source venv/bin/activate && python3 << \"EOF\"
import asyncio
from services.content import generate_article

async def test():
    result = await generate_article(topic=\"Тест\", make_image=False)
    print(\"OK\" if result[\"ok\"] else \"FAIL\")

asyncio.run(test())
EOF
'"

# 3. Логи с фильтрацией
gcloud compute ssh telegram-bot --zone=us-central1-c --project=project-dfb3fb77-77cb-4e79-bbb \
  --command="journalctl -u smoki-bot -n 100 --no-pager | grep -E 'Serper|ERROR'"
```

**⚠️ Важные замечания:**

1. **Экранирование кавычек:** В Python-коде внутри heredoc используйте `\"` для двойных кавычек
2. **F-strings:** Избегайте вложенных f-string с кавычками — используйте `.format()` или конкатенацию:
   ```python
   # WRONG (синтаксис ломается)
   print(f"Text: {dict['key']}")
   
   # RIGHT
   print("Text:", dict['key'])
   print("Text: {}".format(dict['key']))
   ```
3. **Timeout:** Для долгих операций добавьте `--timeout=120000` (120 сек)
4. **Закрытие сессий:** Всегда вызывайте `await close_session()` из `ai.search` после Serper API

---

## 3. Локальная разработка

### 3.1. Setup

```bash
# 1. Clone
git clone <repo-url>
cd SMOKI-git

# 2. Venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Config
cp .env.example .env
# Отредактировать .env: BOT_TOKEN, ADMIN_ID, CHANNEL_ID, etc.

# 4. Init DB
python3 -c "from db.database import init_db; import asyncio; asyncio.run(init_db())"

# 5. Run
python3 bot.py
```

---

### 3.2. Локальные проверки перед push

**Обязательно** прогонять перед каждым push:

```bash
# Lint + typecheck изменённых файлов
venv/bin/ruff check <файлы>
venv/bin/python -m mypy <файлы>

# Полный прогон (как в CI)
venv/bin/ruff check . --exclude venv,data,**pycache**
venv/bin/python -m mypy bot.py config.py db/ ai/ services/ handlers/ scheduler.py

# Автофикс тривиальных замечаний
venv/bin/ruff check <файл> --fix
```

**Версии инструментов:** `ruff==0.15.12`, `mypy==1.14.1` (синхронизировано с CI)

---

### 3.3. Тесты

```bash
# Unit tests
pytest tests/ -v

# С coverage (требуется ≥45%)
pytest --cov --cov-fail-under=45

# Один модуль
pytest tests/test_content.py -v
```

**Smoke tests** (ручная проверка):
```bash
# Генерация статьи
python3 -c "
import asyncio
from services.content import generate_article

async def test():
    result = await generate_article(topic='Тест', make_image=False)
    print('OK' if result['ok'] else 'FAIL')

asyncio.run(test())
"
```

**Правило:** Ценные smoke-проверки оформлять как pytest-тесты (см. `tests/test_stats.py`).

---

## 4. CI/CD

### 4.1. GitHub Actions (10 jobs)

Все jobs должны быть зелёными для merge в `main`:

1. **Python syntax check** — компиляция
2. **Ruff lint** — `ruff==0.15.12`
3. **Bandit security** — `bandit==1.9.4`, `-ll`
4. **pip-audit** — проверка уязвимостей
5. **Pytest + coverage** — `--cov-fail-under=45`
6. **codespell** — проверка орфографии
7. **mypy** — `mypy==1.14.1`
8. **markdown lint** — MD012 и др.
9. **yaml lint**
10. **gitleaks** — поиск секретов

**Branch protection:** `main` защищена, только через PR с зелёным CI.

---

### 4.2. Markdown lint (MD012)

**Проблема:** Множественные пустые строки подряд.

**Правила:**
- Максимум 1 пустая строка подряд
- Убирать trailing spaces
- Файл заканчивается одним `\n`

**Быстрый фикс:**
```bash
python3 -c "import re,sys;p=sys.argv[1];s=open(p).read();open(p,'w').write(re.sub(r'\n{3,}','\n\n',s).rstrip(chr(10))+chr(10))" FILE.md
```

**Локальная проверка (если установлен node):**
```bash
npx markdownlint-cli2 "**/*.md"
```

---

### 4.3. Deployment

**Текущий процесс (manual):**

```bash
# 1. SSH на сервер
gcloud compute ssh telegram-bot --zone=us-central1-c --project=project-dfb3fb77-77cb-4e79-bbb

# 2. Switch user
sudo -u shushpanchik_art -s

# 3. Pull changes
cd /opt/SMOKI/bot
git pull origin main

# 4. Install dependencies (если изменились)
venv/bin/pip install -r requirements.txt

# 5. Restart
sudo systemctl restart smoki-bot

# 6. Verify
journalctl -u smoki-bot -f -n 50
```

**Planned CI/CD (Q1 2027):** Auto-deploy on merge to `main`.

---

## 5. Конфигурация

### 5.1. Environment Variables

**Критичные (обязательны):**
```bash
# Telegram
BOT_TOKEN=<bot-token>
ADMIN_CHAT_ID=<telegram-user-id>
CHANNEL_ID=<channel-id>

# Google AI
GOOGLE_CLOUD_PROJECT=project-xxx
GOOGLE_CLOUD_LOCATION=global
```

**Опциональные:**
```bash
# Serper API (fallback на Google grounding)
SERPER_API_KEY=

# AI Studio fallback
GEMINI_API_KEY_FALLBACK=

# Scheduling
MORNING_START=8
EVENING_START=19
PUBLISH_WINDOW_END=10
```

**Полный список:** см. `.env.example` (51 переменная)

**Проверка на сервере:**
```bash
sudo grep -E '^(GOOGLE_CLOUD_PROJECT|GOOGLE_CLOUD_LOCATION|SERPER_API_KEY)=' /opt/SMOKI/bot/.env
```

---

### 5.2. Database Settings

Редактируемые настройки в таблице `settings` (БД):

```sql
-- Длина постов
morning_facts (1-3) -- кол-во фактов в утреннем посте
evening_words (200-500) -- кол-во слов в вечернем посте

-- Правила контента
liked_feedback -- что нравится админу (стиль)
censor_extra -- накопленные замечания цензуры

-- Scheduler
paused_jobs -- CSV id задач на паузе: "daily_morning,daily_evening"
time_daily_morning -- переопределённый час утренней публикации
time_daily_evening -- переопределённый час вечерней публикации
```

**UI для настроек:** Команды `/setlen`, кнопки в админ-панели (`/start`).

---

## 6. Архитектура (кратко)

**См. детально:** [DESIGN.md](DESIGN.md)

```
bot.py (entry point)
├── handlers/ (команды и callback)
│   ├── admin.py (админ-панель)
│   ├── moderation.py (5 кнопок черновика)
│   └── errors.py (глобальная обработка ошибок)
├── services/ (бизнес-логика)
│   ├── content.py (генерация статей)
│   ├── censor.py (автоцензура)
│   ├── publisher.py (публикация в канал)
│   └── comments_moderator.py (модерация комментариев)
├── ai/ (AI модули)
│   ├── gemini.py (Gemini client)
│   ├── search.py (Serper News API)
│   └── prompts.py (все промпты)
├── db/ (база данных)
│   ├── schema.sql (CREATE TABLE)
│   └── database.py (async CRUD)
└── scheduler.py (APScheduler jobs)
```

**Data flow (генерация утреннего поста):**
```
Scheduler (08:XX) → generate_article() → Serper News API (если новостная тема)
→ Gemini (текст) → Censor (проверка) → Gemini (картинка) → save to DB
→ send_for_moderation() → Админ нажимает ✅ → publish_article() → Канал
```

---

## 7. AI Integration

### 7.1. Google Gemini

**Primary:** Vertex AI (Workload Identity, service account)  
**Fallback:** AI Studio (API key в `.env`)

**Модели:**
- `gemini-3.1-flash-lite` — генерация текста (primary)
- `gemini-1.5-flash-002` — fallback model
- `imagen-3.0-fast-generate-001` — генерация картинок

**Features:**
- Google Search grounding (`use_search=True`)
- Safety settings (medium threshold)
- JSON mode (structured output)

---

### 7.2. Serper News API

**Endpoint:** `https://google.serper.dev/news`

**Использование:**
- Новостные темы (ключевые слова: `новост*`, `событи*`, `заявил*`, `запрет*`, `закон*`)
- Последние 7 дней
- Извлечение `imageUrl` для картинок новостей

**Fallback:** Google Search grounding (если `SERPER_API_KEY` отсутствует или API недоступен)

**Free tier:** 2,500 запросов/мес (текущая нагрузка ~60-100/мес)

---

## 8. Контент-план

**Утро (08:00-10:00 MSK):**
- 1-3 факта (настраивается)
- Обязательная короткая шутка в конце
- 100-150 слов (строго)
- Картинка (AI-генерация или из Serper imageUrl)

**Вечер (19:00-20:30 MSK):**
- Лонг-рид 200-500 слов (настраивается)
- Глубокая проработка темы
- Картинка (AI-генерация или из Serper imageUrl)
- Возможность Saga-эпизода (если `SAGA_ENABLED=1`)

**Модерация:**
- Черновик отправляется админу в ЛС
- 5 кнопок: ✅ Опубликовать / 🔄 Регенерировать текст / 🖼 Регенерировать картинку / 📝 Редактировать / ⛔ Отмена
- Автопубликация по дедлайну (10:00 и 20:30) если не промодерировано

**Автоцензура:**
- ❌ Призыв к покупке и курению
- ❌ Медицинские советы
- ❌ Утверждения о пользе курения
- ✅ Нейтральное упоминание брендов (разрешено)

---

## 9. Troubleshooting

### 9.1. Бот не отвечает

```bash
# 1. Проверка процесса
sudo systemctl status smoki-bot

# 2. Логи (последние 100 строк)
journalctl -u smoki-bot -n 100 --no-pager

# 3. Ошибки
journalctl -u smoki-bot | grep ERROR | tail -20

# 4. Перезапуск
sudo systemctl restart smoki-bot
```

---

### 9.2. Задачи планировщика не выполняются

```bash
# 1. Проверка heartbeat
journalctl -u smoki-bot | grep HEARTBEAT | tail -5

# 2. Проверка jobstore (SQLite)
sqlite3 /opt/SMOKI/bot/data/smoki.db "SELECT id, next_run_time FROM apscheduler_jobs;"

# 3. Restart + verify
sudo systemctl restart smoki-bot
journalctl -u smoki-bot -f
```

---

### 9.3. API ошибки (Gemini/Serper)

**Gemini HTTP 503:**
```
Symptom: "google.api_core.exceptions.ServiceUnavailable"
Cause: Vertex AI недоступен
Fix: Автоматический fallback на AI Studio key
```

**Serper HTTP 429:**
```
Symptom: "Serper API ошибка (fallback на grounding)"
Cause: Rate limit exceeded (2500 req/мес)
Fix: Автоматический fallback на Google grounding
```

**Проверка fallback:**
```bash
journalctl -u smoki-bot | grep -E "резервный ключ|fallback" | tail -10
```

---

### 9.4. База данных заблокирована

```
Symptom: sqlite3.OperationalError: database is locked
Cause: Concurrent write (редко при SQLite)
Fix: Restart бота (pending writes завершатся)
```

**Prevention:** SQLite jobstore (persistent) автоматически retry.

---

## 10. Мониторинг

### 10.1. Heartbeat

**Как работает:**
1. APScheduler job пишет "HEARTBEAT ok" каждые 4 часа
2. Systemd timer проверяет журнал каждый час
3. Если нет heartbeat >8 часов → алерт админу в Telegram

**Проверка:**
```bash
# Последний heartbeat
journalctl -u smoki-bot | grep HEARTBEAT | tail -1

# Проверка таймера
systemctl status smoki-heartbeat.timer
```

---

### 10.2. AI Budget

**Команда:** `/stats` в боте

**Результат:**
```
📊 Статистика AI (октябрь 2026)

Текст: 1,234,567 токенов ($0.12)
Картинки: 45 шт ($0.45)

Итого: $0.57 / $10.00 бюджет (5.7%)

Прогноз на месяц: $1.75 (в рамках бюджета ✅)
```

**Alert:** Если >80% бюджета → предупреждение в `/stats`.

---

### 10.3. Backup

**Автоматический:**
- Ежедневно в 03:00 UTC (06:00 MSK)
- Retention: 30 дней
- Содержимое: `data/smoki.db` + `data/images/`
- Проверка: systemd timer отправляет сводку админу (23:45 MSK)

**Ручной:**
```bash
# Trigger backup
sudo systemctl start smoki-backup.service

# Проверка результата
journalctl -u smoki-backup.service -n 50 --no-pager | grep -E "backup ok|stats:"
```

**Restore:**
```bash
# 1. Stop bot
sudo systemctl stop smoki-bot

# 2. Restore from backup
cd /opt/SMOKI/bot
tar -xzf /opt/SMOKI/backups/backup_YYYYMMDD.tar.gz

# 3. Start bot
sudo systemctl start smoki-bot
```

---

## 11. Known Issues

**ISSUE-001: Длинные новостные посты без imageUrl**  
- Частота: <5%
- Workaround: AI-генерация картинки
- Статус: Won't fix

**ISSUE-002: Saga теряет контекст между эпизодами**  
- Частота: ~10%
- Workaround: Ручная корректировка `saga_state.recap`
- Статус: Known limitation (LLM context window)

---

## 12. Документация

**Навигация:**
- [PRD.md](PRD.md) — продуктовые требования (что и зачем)
- [TRD.md](TRD.md) — технические требования (как реализовано)
- [FLOW.md](FLOW.md) — пользовательские сценарии
- [DESIGN.md](DESIGN.md) — архитектура системы (компоненты, data flow)
- [DB.md](DB.md) — схема базы данных (таблицы, индексы)
- [PLAN.md](PLAN.md) — roadmap и план развития
- [PROJECT_BOOK.md](PROJECT_BOOK.md) — полная книга проекта (история, lessons learned)
- [TESTING.md](TESTING.md) — руководство по тестированию
- [RESEARCH_NEWS_SEARCH_API.md](RESEARCH_NEWS_SEARCH_API.md) — исследование Serper API
- [SMOKE_TESTS.md](SMOKE_TESTS.md) — smoke-тесты для production

---

**Версия:** 2.0 (13 октября 2026)  
**Автор:** @shushpanchik_art  
**Лицензия:** Proprietary

**Изменения от 1.0:**
- Разделение документации на специализированные файлы
- Фокус SPEC.md на практических аспектах для разработчика
- Удаление дублирования (детали в PRD/TRD/DESIGN/DB)
- Добавление навигации между документами
