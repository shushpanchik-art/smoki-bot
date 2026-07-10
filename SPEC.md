
## Локальные проверки перед push (обязательно)

ruff установлен в venv (`ruff==0.15.12`, версия синхронна с CI). mypy тоже в venv.

Перед КАЖДЫМ push прогнать:

venv/bin/ruff check <изменённые_файлы> && venv/bin/python -m mypy <изменённые_файлы>

Автоисправление тривиальных замечаний ruff:

venv/bin/ruff check <файл> --fix

Полный прогон как в CI (джоба Ruff lint):

venv/bin/ruff check . --exclude venv,data,__pycache__

Это ловит ошибки (F541, неиспользуемые импорты и т.п.) до GitHub Actions и экономит запуски CI. Версии ruff/mypy в venv обязаны совпадать с CI: ruff==0.15.12, mypy==1.14.1.


## Smoke-тесты vs pytest

Ручной smoke (`python -c "asyncio.run(...)"`) — разовая проверка при разработке,
ловит баги до PR и экономит запуски CI. В CI НЕ входит.

Правило: ценную smoke-проверку оформлять постоянным pytest-тестом
(изоляция БД через фикстуру `tmp_db` из tests/conftest.py + `await db.init_db()`).
Пример: tests/test_stats.py.

## Админ-панель (inline)

/start у админа показывает inline-меню (callback namespace `adm_*`):
генерация обычный/утро/вечер, статистика (db.get_stats), длина постов,
правила «нравится»/цензуры. Хелпер `_cb_msg` сужает Message|InaccessibleMessage.
