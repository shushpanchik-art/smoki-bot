"""Тесты конфигурации: ключевые константы объявлены и валидны."""
import config


def test_required_attrs_exist():
    for attr in [
        "BOT_TOKEN", "CHANNEL_ID", "DB_PATH", "GEMINI_API_KEY",
        "GEMINI_TEXT_MODEL", "GEMINI_IMAGE_MODEL", "CATEGORIES",
        "PUBLISH_HOUR", "MAX_REGEN",
    ]:
        assert hasattr(config, attr), f"нет config.{attr}"


def test_categories_nonempty_list():
    assert isinstance(config.CATEGORIES, list)
    assert len(config.CATEGORIES) > 0


def test_int_helper_fallback(monkeypatch):
    monkeypatch.delenv("NONEXISTENT_KEY", raising=False)
    assert config._int("NONEXISTENT_KEY", 42) == 42


def test_int_helper_invalid_value(monkeypatch):
    monkeypatch.setenv("BAD_INT", "notanumber")
    assert config._int("BAD_INT", 7) == 7


def test_models_not_empty():
    assert config.GEMINI_TEXT_MODEL
    assert config.GEMINI_IMAGE_MODEL
