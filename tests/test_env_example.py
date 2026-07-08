"""Проверка, что .env.example содержит все критичные ключи из config.py."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _config_keys() -> set[str]:
    src = (ROOT / "config.py").read_text(encoding="utf-8")
    return set(re.findall(r'os\.getenv\(\s*["\']([A-Z0-9_]+)["\']', src))


def _example_keys() -> set[str]:
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    keys = set()
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


def test_env_example_exists():
    assert (ROOT / ".env.example").exists()


def test_all_config_keys_in_env_example():
    missing = _config_keys() - _example_keys()
    assert not missing, f"В .env.example не хватает ключей: {sorted(missing)}"
