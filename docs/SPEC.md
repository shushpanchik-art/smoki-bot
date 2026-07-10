# SMOKI-bot

## Назначение

Автоведение Telegram-канала @SMOKTOLK (вейпы, кальяны, табак) с AI-генерацией контента, ручной модерацией и автомодерацией комментариев.

## Инфраструктура

- Путь: /opt/SMOKI/bot, venv venv/bin/python
- systemd: smoki-bot (Restart=always), режим polling
- Python 3.11.2, aiogram 3.29.1, aiosqlite, apscheduler, dotenv
- БД smoki.db: published_topics, articles, comments, ai_logs, settings
- Управление: systemctl restart smoki-bot; journalctl -u smoki-bot -n50

## AI

- google-genai через Vertex AI (USE_VERTEXAI=true, ADC service account)
- Резерв AI Studio по ключу GEMINI_API_KEY_FALLBACK
- Модели: gemini-2.5-flash (текст), gemini-2.5-flash-image (картинки)

## Контент-план (Europe/Moscow)

- Утро (8-10): 1-3 факта плюс авторский комментарий, до 120 слов, картинка.
- Вечер (19-20): лонг-рид 200-500 слов (деф. 350), картинка.
- Оба поста проходят автоцензуру и ручную модерацию (опубликовать / регенерировать / отклонить). При простое автопубликация по дедлайну.
- Длина настраивается: /setlen morning N (1-3), /setlen evening N (200-500).
- Ручная генерация (админ, ЛС): /generate (обычный), /generate_morning (утро+шутка), /generate_evening (лонг-рид). Reply-клавиатура на /start дублирует команды.
- Время суток в промпт передаётся по фактическому времени генерации (daytime_label по локальному часу сервера), а не по жёстко зашитым окнам.
- Утренний пост ОБЯЗАТЕЛЬНО завершается короткой остроумной шуткой по теме.
- Grounding: тело статьи генерируется с Google Search (use_search=True в generate_text) — модель опирается на свежие материалы из интернета. Темы, цензура, картинки — без поиска.

## Комментарии

- Автомодерация в DISCUSSION_GROUP_ID каждые COMMENTS_INTERVAL_HOURS.
- Классы: reklama / toxic / question / neutral / positive.
- Ответы на question/neutral/positive; удаление reklama/toxic.

## Автоцензура

Нет призыва к покупке и курению; нет медсоветов; не утверждать пользу курения. Разрешено нейтральное упоминание брендов.

## Структура

- bot.py, config.py, scheduler.py
- db (schema.sql, database.py)
- ai (gemini.py, prompts.py)
- services (content.py, publisher.py, comments.py)
- handlers (admin.py, group.py, ROUTERS)
- scripts/ai_healthcheck.py

## CI

7 джоб: syntax, ruff, bandit, pip-audit, pytest (cov 45), codespell, mypy. main защищён, только через PR с зелёным CI. .env.example содержит все ключи config.py.
