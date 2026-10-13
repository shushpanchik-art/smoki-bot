# SMOKI-bot

Автоматизированное ведение Telegram-канала [@SMOKTOLK](https://t.me/SMOKTOLK) с AI-генерацией контента, модерацией и планированием публикаций.

## О проекте

SMOKI-bot — это AI-powered система автоведения Telegram-канала о вейпах, кальянах и табаке. Бот генерирует контент с помощью Google Gemini, модерирует комментарии, публикует посты по расписанию и ведет генеративный сюжетный сериал (SAGA).

**Основные возможности:**

- 🤖 **AI-генерация контента**: Gemini 2.5 Flash через Vertex AI с автоцензурой
- 📅 **Автоматическое расписание**: 2 поста в день (утро + вечер) с модерацией
- 💬 **Автомодерация комментариев**: классификация и автоответы
- 📖 **SAGA**: генеративный сюжетный сериал по Кругу Хармона
- 📊 **Админ-панель**: inline-управление через Telegram
- 💰 **Контроль расходов AI**: отслеживание стоимости через BigQuery
- 🔄 **Stories** (код готов, заморожено по экономическим причинам)

## Технологии

- **Python 3.11.2** на продакшн (Debian 12, GCP)
- **aiogram 3.30.0** — Telegram Bot API
- **google-genai 2.19.0** — Vertex AI / AI Studio
- **APScheduler 3.11.3** — планирование задач
- **SQLite** (aiosqlite) — хранилище
- **Pillow 12.3.0** — обработка изображений
- **Telethon 1.44.0** — userbot для Stories (MTProto)

Полный список зависимостей: [requirements.txt](requirements.txt)

## Быстрый старт

### Требования

- Python 3.11.2+
- SQLite 3
- Google Cloud credentials (для Vertex AI) или Gemini API key

### Установка

```bash
# Клонирование репозитория
git clone https://github.com/shushpanchik-art/smoki-bot.git
cd smoki-bot

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt
pip install -r requirements-dev.txt  # для разработки

# Настройка окружения
cp .env.example .env
# Отредактируйте .env и заполните необходимые токены
```

### Конфигурация

Основные переменные в `.env`:

```bash
# Telegram
BOT_TOKEN=your_bot_token
CHANNEL_ID=@SMOKTOLK
ADMIN_CHAT_ID=your_telegram_id

# AI (Vertex AI или AI Studio)
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your_gcp_project
GEMINI_API_KEY_FALLBACK=your_fallback_key

# База данных
DB_PATH=/path/to/smoki.db
```

Полный список параметров см. в [.env.example](.env.example)

### Запуск

```bash
# Инициализация БД (автоматически при первом запуске)
python bot.py

# Или через systemd на продакшн (см. deploy/systemd/)
```

## Разработка

### Проверки перед коммитом

```bash
# Линтеры и типы
venv/bin/ruff check . --exclude venv,data,__pycache__
venv/bin/python -m mypy bot.py config.py db/ ai/ services/ handlers/ scheduler.py

# Тесты
venv/bin/python -m pytest --cov --cov-fail-under=45

# Markdown lint
npx markdownlint-cli2 "**/*.md"
```

### CI/CD

Проект использует GitHub Actions с 10 обязательными проверками:

1. Python syntax check
2. Ruff lint
3. Bandit security scan
4. pip-audit
5. Pytest + coverage (≥45%)
6. codespell
7. mypy type check
8. markdown lint
9. yaml lint
10. gitleaks secret scan

Все проверки должны быть зелеными для merge в `main`.

### Структура проекта

```
smoki-bot/
├── bot.py              # Точка входа
├── config.py           # Конфигурация из .env
├── scheduler.py        # APScheduler задачи
├── userbot.py          # Telethon userbot для Stories
├── ai/                 # AI-генерация
│   ├── gemini.py       # Vertex AI + AI Studio
│   └── prompts.py      # Промпты для генерации
├── db/                 # База данных
│   ├── database.py     # CRUD-операции
│   └── schema.sql      # Схема SQLite
├── handlers/           # Telegram обработчики
│   ├── admin.py        # Админ-панель
│   └── group.py        # Группа обсуждений
├── services/           # Бизнес-логика
│   ├── content.py      # Генерация статей
│   ├── publisher.py    # Публикация в канал
│   ├── comments.py     # Модерация комментариев
│   ├── saga.py         # Генеративный сериал
│   ├── stories.py      # Stories (заморожено)
│   ├── schedule_*.py   # Управление расписанием
│   └── billing.py      # BigQuery расходы
├── tests/              # Pytest тесты
├── scripts/            # Утилиты (бэкапы, алерты)
├── deploy/systemd/     # Systemd юниты
└── docs/               # Документация
    ├── SPEC.md         # Полная спецификация (690 строк)
    ├── TESTING.md      # Гайд по тестированию
    └── WORKLOG.md      # Журнал разработки
```

## Документация

- 📋 **[SPEC.md](docs/SPEC.md)** — полная техническая спецификация (инфраструктура, функционал, API)
- 🧪 **[TESTING.md](docs/TESTING.md)** — гайд по тестированию и CI
- 📝 **[WORKLOG.md](docs/WORKLOG.md)** — журнал работ и статусы задач
- 📦 **[PROJECT_BOOK.txt](docs/PROJECT_BOOK.txt)** — расширенная документация и история проекта

## Деплой

### GCP (продакшн)

```bash
# Сервер: Debian 12, us-central1-c
# Путь: /opt/SMOKI/bot

# Systemd сервисы
sudo systemctl restart smoki-bot      # Основной бот
sudo systemctl status smoki-userbot   # Stories userbot (если активен)

# Логи
journalctl -u smoki-bot -n 50 --no-pager

# Бэкапы (автоматические через systemd timers)
sudo systemctl list-timers 'smoki-*'
```

Детали деплоя см. в [SPEC.md § Инфраструктура](docs/SPEC.md#инфраструктура)

## Безопасность

- 🔐 Секреты только в `.env` (в `.gitignore`)
- 🔍 Gitleaks сканирование в CI
- 🛡️ Bandit security scan
- 📦 pip-audit для уязвимостей зависимостей
- ⚠️ Stories используют MTProto (Telethon) — **риск блокировки аккаунта** согласован с владельцем

## Лицензия

© 2024-2026 Артемий Вишневский ([@shushpanchik_art](https://t.me/shushpanchik_art))

Все права защищены. Подробности см. в файле [LICENSE](LICENSE).

## Контакты

Вопросы и предложения: [@shushpanchik_art](https://t.me/shushpanchik_art)

---

⚡ Powered by [Google Gemini](https://ai.google.dev/) · Built with [aiogram](https://github.com/aiogram/aiogram)
