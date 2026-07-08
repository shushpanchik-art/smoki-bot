# SPEC — SMOKI-bot

> Живой документ проекта: техзадание + фактическое состояние + системный
> контекст для ассистента. Обновлять при каждом значимом изменении.
> Статусы: **[DONE]** реализовано · **[PARTIAL]** частично · **[TODO]** нет ·
> **[CHANGED]** отличается от исходного ТЗ.

## 1. Цель

SMOKI — Telegram-канal (@SMOKTOLK): вейпы, кальяны, табак, безникотиновые
альтернативы. Бот генерирует контент через Google GenAI (текст + изображение),
проходит ручную модерацию админом, публикует по расписанию и (в перспективе)
модерирует комментарии в группе-обсуждении. Бизнес-цель — набор аудитории.

Размещение: `/opt/SMOKI/bot`, изоляция от smoktolk (свой venv, БД `smoki.db`,
юнит `smoki-bot.service`, порт 8082 зарезервирован). Режим — **polling**.

## 2. Стек

aiogram 3.29.1 · aiosqlite · apscheduler · python-dotenv · google-genai.
Python 3.11.2 (сервер). systemd `Restart=always`.

## 3. AI-интеграция [CHANGED]

Через **Vertex AI**, а не AI Studio. Ключ `GEMINI_API_KEY` в проде не нужен.

| Переменная | Дефолт |
| --- | --- |
| `GOOGLE_GENAI_USE_VERTEXAI` | `false` (в проде `true`) |
| `GOOGLE_CLOUD_PROJECT` | — |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` |
| `GEMINI_TEXT_MODEL` | `gemini-2.5-flash` |
| `GEMINI_IMAGE_MODEL` | `gemini-2.5-flash-image` |

`ai/gemini.py` — тонкий слой: `get_client()` (синглтон, `genai.Client()` без
аргументов, креды из окружения), `generate_text(prompt, *, temperature=0.9)`,
`generate_image(prompt) -> bytes | None`. Вся прикладная логика — в services.
`ai/prompts.py` — все промпты (тема, статья, image-prompt, цензура, комменты).

## 4. Функциональные требования (статус)

- **FR-1 Генерация статьи [DONE]** — `services/content.generate_article()`,
  тема из ротации категорий, в промпт передаются использованные темы.
- **FR-2 Цензура текста [DONE]** — `services/content.censor() -> (ok, text)`,
  AI-ревьюер; при провале регенерация до `MAX_REGEN`.
- **FR-3 Генерация изображения [PARTIAL]** — `content._image()` есть; отдельный
  review_image (проверка на лица/логотипы) не выделен.
- **FR-4 Модерация админом [DONE, CHANGED]** — inline-кнопки:
  ✅ Опубликовать (`pub:`) · 🔄 Заново (`regen:`) · ❌ Отклонить (`rej:`).
  Команды `/start`, `/generate`, `/id`. Отдельной кнопки «Замечания» нет.
- **FR-5 Публикация [DONE]** — `services/publisher.publish_article()`;
  `_split()` режет текст под лимит Telegram по границам абзацев.
- **FR-6 Модерация комментариев [PARTIAL]** — `handlers/group.py`
  `collect_group_message()` складывает сообщения группы в БД `comments`.
  Классификация AI и джоб раз в N часов — **[TODO]**.
- **FR-7 Уникальность и учёт [DONE]** — `published_topics` (+`topic_hash`),
  `ai_logs` (`log_ai`).

## 5. Архитектура (факт)

    bot.py            # polling, Dispatcher, ROUTERS, scheduler.start()
    config.py         # чтение .env (_int-хелпер, дефолты-плейсхолдеры)
    scheduler.py      # apscheduler, TZ=Europe/Moscow
    db/schema.sql     # DDL, все CREATE ... IF NOT EXISTS
    db/database.py    # aiosqlite: init_db + CRUD
    ai/gemini.py      # клиент GenAI (get_client/generate_text/generate_image)
    ai/prompts.py     # промпты
    services/content.py    # generate_topic/generate_article/censor/_clean_html
    services/publisher.py  # publish_article/_split
    handlers/admin.py      # команды + модерация (callbacks)
    handlers/group.py      # приём сообщений группы -> БД
    handlers/__init__.py   # ROUTERS = [...]
    scripts/ai_healthcheck.py
    tests/            # см. docs/TESTING.md

Примечание: отдельного `services/comments.py` нет — сбор в `group.py`
(обработка [TODO]).

## 6. База данных (SQLite) [CHANGED: +settings]

Таблицы: `published_topics`, `articles`, `comments`, `ai_logs`, **`settings`**.
Все `CREATE ... IF NOT EXISTS` (идемпотентно). `settings(key PK, value,
updated_at)` — рантайм-флаги (CRUD `get_setting`/`set_setting`).

CRUD (db/database.py): `init_db`, `topic_hash`, `get_used_topics`, `add_topic`,
`set_topic_status`, `add_article`, `get_article`, `update_article`,
`get_approved_article`, `get_latest_pending_article`, `add_comment`,
`get_new_comments`, `update_comment`, `log_ai`, `get_setting`, `set_setting`.

## 7. Конфигурация (.env) [CHANGED: окна вместо PUBLISH_HOUR]

Telegram: `BOT_TOKEN`, `CHANNEL_ID`, `DISCUSSION_GROUP_ID`, `ADMIN_CHAT_ID`.
GenAI: `GEMINI_API_KEY`, `GEMINI_TEXT_MODEL`, `GEMINI_IMAGE_MODEL`,
`GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`.
Хранилище: `DB_PATH`, `IMAGE_DIR`. Сеть/расписание: `WEBHOOK_PORT` (8082),
`PUBLISH_HOUR`, `COMMENTS_INTERVAL_HOURS`, `MAX_REGEN`.
Окна (часы, локальное время): `GEN_WINDOW_START/END`,
`PUBLISH_WINDOW_START/END`.

`.env` в `.gitignore`; `.env.example` синхронен с `config.py`
(проверяет `test_env_example`).

## 8. Планировщик [CHANGED]

`scheduler.start(bot)` (синглтон), TZ **Europe/Moscow**, 2 джобы:

- `daily_generate` — cron в `GEN_WINDOW_START` + случайная минута.
- `publish_deadline` — cron в `PUBLISH_WINDOW_END:00` (автопубликация одобренного).

Джоб обработки комментариев (каждые `COMMENTS_INTERVAL_HOURS`) — **[TODO]**.

## 9. Нефункциональные

Автономность (`Restart=always`) · секреты только в `.env` · глобальный
error-handler + try/except вокруг AI · модульность слоёв · изоляция от smoktolk.

## 10. Дальнейшие шаги (Roadmap)

1. **FR-6 завершить:** `classify_comment` (реклама/токсик/вопрос/позитив) +
   действия (удалить/ответить) + джоб раз в `COMMENTS_INTERVAL_HOURS`.
2. **FR-3 усилить:** review_image (лица/логотипы/провокация) + регенерация.
3. Учёт стоимости в `ai_logs` (`est_cost_usd`) при каждом вызове.
4. Прод-проверка Vertex AI на канале (генерация -> модерация -> публикация).

## 11. Системный контекст (для ассистента)

- **Проект активен по рабочей папке.** SMOKI = `/opt/SMOKI/bot`, venv
  `venv/bin/python`, юнит `smoki-bot`. Второй проект — smoktolk
  (`/opt/smoktolk/bot`, webhook/aiohttp) — не путать.
- **Управление:** `systemctl restart|status smoki-bot`,
  `journalctl -u smoki-bot -n50`.
- **Git-flow:** `main` защищён, прямой push запрещён. Ветка
  `feature/|fix/|chore/|docs/` -> commit -> push -> `gh pr create` ->
  зелёный CI -> merge в UI. Всегда проверять синтаксис
  (`python3 -c "import ast; ast.parse(open('f.py').read())"`).
- **CI — 10 джоб:** syntax, ruff, bandit (-ll), pip-audit,
  pytest (`--cov-fail-under=45`), codespell, mypy (bot/config/db/ai/services/
  handlers/scheduler), gitleaks (`.gitleaks.toml`), yamllint (`.yamllint`),
  markdownlint (`.markdownlint.json`, `**/*.md`).
- **Тесты:** см. `docs/TESTING.md` (14 файлов, AI мокается).
- **Репозиторий:** приватный `git@github.com:shushpanchik-art/smoki-bot.git`.
- **Правила:** пользователь не программист -> готовые шаги/код, MVP. Не писать
  код по предположениям — сначала `ls/grep/cat`. Не видел файл -> разведать.
