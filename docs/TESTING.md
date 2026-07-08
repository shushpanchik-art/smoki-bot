# Тестирование SMOKI-bot

## Запуск локально

    cd /opt/SMOKI/bot
    venv/bin/pip install -r requirements-dev.txt   # один раз
    venv/bin/python -m pytest --cov --cov-report=term-missing

## Что покрыто (27 тестов)

- `tests/test_config.py` — наличие констант, `_int` fallback, модели не пустые.
- `tests/test_content.py` — `_split` (лимит Telegram), `_clean_html`, censor (моки AI).
- `tests/test_db.py` — init_db создаёт таблицы, topic_hash, CRUD тем, дедуп.
- `tests/test_import.py` — smoke: все модули импортируются, ROUTERS непустой.

## Фикстуры (conftest.py)

- Заглушки `BOT_TOKEN` / `GEMINI_API_KEY` — CI без .env.
- `tmp_db` — временная SQLite + подмена DB_PATH и пути схемы.

## Конфиг

- `pytest.ini` — asyncio auto-mode, loop scope=function.

## Правила

- AI-вызовы мокаются, реальный API в тестах не дёргается.
- Новый модуль -> smoke-тест на импорт + тесты чистых функций.
