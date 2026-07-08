import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Заглушки для секретов, чтобы config/gemini не падали в CI без .env
os.environ.setdefault("BOT_TOKEN", "123:TEST")
os.environ.setdefault("GEMINI_API_KEY", "test-key")


@pytest.fixture
def tmp_db(monkeypatch):
    """Временная БД + подмена хардкод-пути схемы на реальный из репо."""
    import config
    from db import database as db

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(db, "_SCHEMA_PATH", str(ROOT / "db" / "schema.sql"))
    yield path
    if os.path.exists(path):
        os.remove(path)
