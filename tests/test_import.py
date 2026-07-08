"""Smoke-тесты: модули импортируются без падения."""
import importlib

MODULES = [
    "config",
    "db.database",
    "ai.gemini",
    "ai.prompts",
    "services.content",
    "services.publisher",
    "handlers",
    "scheduler",
    "bot",
]


def test_all_modules_import():
    for name in MODULES:
        importlib.import_module(name)


def test_routers_is_iterable():
    from handlers import ROUTERS
    assert isinstance(ROUTERS, (list, tuple))
    assert len(ROUTERS) > 0
