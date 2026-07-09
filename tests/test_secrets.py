"""Проверка, что секреты не утекли в трекнутые файлы репозитория."""
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

# Паттерны реальных секретов (НЕ дефолтов-заглушек)
_SECRET_PATTERNS = [
    re.compile(r"\b\d{6,}:AA[\w-]{30,}\b"),          # Telegram bot token
    re.compile(r"AIza[\w-]{30,}"),                    # Google API key
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),  # PEM ключ
]

# Значения-заглушки, которые допустимы в коде/тестах
_ALLOWED = {"123:TEST", "test-key", ""}


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [f for f in out.stdout.splitlines() if f]


def test_env_is_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore, ".env должен быть в .gitignore"


def test_env_not_tracked():
    tracked = _tracked_files()
    assert ".env" not in tracked, ".env НЕ должен быть в git!"


def test_no_secret_patterns_in_tracked_files():
    leaks = []
    for rel in _tracked_files():
        p = ROOT / rel
        if not p.is_file() or p.suffix in {".png", ".jpg", ".db", ".ico"}:
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in _SECRET_PATTERNS:
            for m in pat.findall(content):
                if m not in _ALLOWED:
                    leaks.append(f"{rel}: {m[:12]}...")
    assert not leaks, f"Возможная утечка секретов: {leaks}"


def test_config_defaults_are_placeholders():
    """Дефолтные значения секретов в config должны быть пустыми (не реальными)."""
    import config
    assert config.BOT_TOKEN in _ALLOWED or ":" not in config.BOT_TOKEN[:20]
    assert config.GEMINI_API_KEY in _ALLOWED or not config.GEMINI_API_KEY.startswith("AIza")
