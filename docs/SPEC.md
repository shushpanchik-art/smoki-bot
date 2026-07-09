# SMOKI-bot — Спецификация

## Назначение

Автоведение Telegram-канала @SMOKTOLK (вейпы, кальяны, табак,
безникотиновые альтернативы, культура курения) с AI-генерацией контента,
модерацией через админа и автомодерацией комментариев в группе-обсуждении.

## Инфраструктура

- Путь: `/opt/SMOKI/bot`, venv `/opt/SMOKI/bot/venv/bin/python`
- systemd: `smoki-bot` (Restart=always), режим polling
- Python 3.11.2, aiogram 3.29.1, aiosqlite, apscheduler, dotenv
- БД: `smoki.db` — таблицы published_topics, articles, comments, ai_logs, settings
- Управление: `systemctl restart|status smoki-bot`, `journalctl -u smoki-bot -n50`

## AI

- google-genai через Vertex AI (`USE_VERTEXAI=true`, ADC service account)
- Резерв: AI Studio по ключу `GEMINI_API_KEY_FALLBACK` (авто-переключение
  в `ai/gemini.py` при ошибке Vertex — лимит/safety-блок)
- Модели: `GEMINI_TEXT_MODEL=gemini-2.5-flash`,
  `GEMINI_IMAGE_MODEL=gemini-2.5-flash-image`

## Контент-план (Europe/Moscow)

- **Утро (MORNING_START–MORNING_END, деф. 8–10):** 1–3 любопытных факта +
  остроумный авторский комментарий, до ~120 слов, + картинка.
- **Вечер (EVENING_START–EVENING_END, деф. 19–20):** лонг-рид 200–500 слов
  (деф. 350) + картинка.
- Оба поста проходят автоцензуру и **ручную модерацию** (кнопки:
  опубликовать / регенерировать / отклонить). При простое — автопубликация
  по дедлайну `PUBLISH_WINDOW_END`.
- Длина настраивается из админки: `/setlen morning N` (1–3),
  `/setlen evening N` (200–500) → сохраняется в таблице settings.

## Комментарии

- Автомодерация в `DISCUSSION_GROUP_ID` каждые `COMMENTS_INTERVAL_HOURS`.
- Классификация: reklama / toxic / question / neutral / positive.
- Ответы бота на question/neutral/positive; удаление reklama/toxic.

## Автоцензура (жёсткие запреты)

Нет call-to-action на покупку; нет призыва курить/употреблять никотин;
нет медсоветов; не утверждать безопасность/пользу курения.
Разрешено: нейтральное упоминание брендов в познавательном контексте.

## Структура


bot.py, config.py, scheduler.py
db/(schema.sql, database.py)
ai/(gemini.py, prompts.py)
services/(content.py, publisher.py, comments.py)
handlers/(admin.py, group.py, __init__→ROUTERS)
scripts/ai_healthcheck.py

CI (7 джоб)
syntax check, ruff==0.15.12, bandit==1.9.4 (-ll), pip-audit,
pytest --cov-fail-under=45, codespell, mypy==1.14.1.
main защищён — только через PR с зелёным CI. .env.example содержит
все ключи из config.py (проверяется тестом test_env_example).
