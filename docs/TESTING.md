# Тестирование SMOKI-bot

## Запуск локально

    cd /opt/SMOKI/bot
    venv/bin/pip install -r requirements-dev.txt   # один раз
    venv/bin/python -m pytest --cov --cov-report=term-missing

## CI (10 джоб, .github/workflows/ci.yml)

1. **Python syntax check** — компиляция всех `.py`.
2. **Ruff lint** — стиль/ошибки.
3. **Bandit security scan** — статический анализ безопасности.
4. **pip-audit** — уязвимости в `requirements.txt`.
5. **Pytest** — тесты + coverage, порог `--cov-fail-under=45`.
6. **codespell** — опечатки.
7. **mypy type check** — типы (`bot.py config.py db/ ai/ services/ handlers/ scheduler.py`).
8. **gitleaks secret scan** — сканер секретов по истории (`.gitleaks.toml`).
9. **yaml lint** — линт YAML (`.yamllint`, relaxed).
10. **markdown lint** — линт `**/*.md` (`.markdownlint.json`).

## Тесты (tests/)

- `test_config.py` — константы, `_int` fallback, модели не пустые.
- `test_content.py` — `_split` (лимит Telegram), `_clean_html`, censor (моки AI).
- `test_publisher.py` — `_split` по границам абзацев, без переполнения.
- `test_db.py` — init_db создаёт таблицы, topic_hash, CRUD тем, дедуп.
- `test_schema.py` — все таблицы/колонки, идемпотентность, `IF NOT EXISTS`.
- `test_integrity.py` — уникальность тем/комментов, нормализация hash.
- `test_import.py` — smoke: все модули импортируются, ROUTERS итерируем.
- `test_routers.py` — ROUTERS непустой, экземпляры Router, уникальны.
- `test_prompts.py` — промпты содержат обязательные плейсхолдеры, не пустые.
- `test_gemini.py` — моки API: пустой ответ -> "", нет картинки -> None, клиент-синглтон.
- `test_scheduler.py` — `_random_minute` в диапазоне, регистрируются 2 джобы, синглтон.
- `test_secrets.py` — `.env` в `.gitignore` и не в git; нет паттернов ключей в трекнутом; дефолты config — плейсхолдеры.
- `test_env_example.py` — `.env.example` синхронен с ключами `config.py`.
- `test_sql_valid.py` — schema.sql исполняется в in-memory SQLite (битый DDL, идемпотентность, `IF NOT EXISTS`).

## Фикстуры (conftest.py)

- Заглушки `BOT_TOKEN` / `GEMINI_API_KEY` — CI без .env.
- `tmp_db` — временная SQLite + подмена DB_PATH и пути схемы.

## Конфиг

- `pytest.ini` — asyncio auto-mode, loop scope=function.
- `.coveragerc`, `mypy.ini` — настройки покрытия и типов.

## Правила

- AI-вызовы мокаются, реальный API в тестах не дёргается.
- Новый модуль -> smoke-тест на импорт + тесты чистых функций.
- Секреты только в `.env` (в `.gitignore`); в трекнутых файлах — плейсхолдеры.
