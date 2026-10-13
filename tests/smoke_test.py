#!/usr/bin/env python3
"""Smoke-тестирование основных компонентов бота.

Проверяет:
- Конфигурацию и переменные окружения
- Доступность базы данных
- Работоспособность AI модулей (Gemini, Serper)
- Подключение к Telegram API
- Systemd служб (на сервере)
"""
import asyncio
import sys
from pathlib import Path

# Добавить корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_config():
    """Проверка конфигурации."""
    print("\n[1/6] Проверка конфигурации...")
    try:
        import config

        checks = {
            "BOT_TOKEN": bool(config.BOT_TOKEN),
            "CHANNEL_ID": bool(config.CHANNEL_ID),
            "GEMINI_API_KEY or Vertex": (
                bool(config.GEMINI_API_KEY) or
                config.GOOGLE_GENAI_USE_VERTEXAI == "true"
            ),
            "DB_PATH": bool(config.DB_PATH),
            "IMAGE_DIR": bool(config.IMAGE_DIR),
        }

        all_ok = all(checks.values())

        for key, status in checks.items():
            status_icon = "✅" if status else "❌"
            print(f"  {status_icon} {key}")

        if config.SERPER_API_KEY:
            print(f"  ✅ SERPER_API_KEY (optional)")
        else:
            print(f"  ⚠️  SERPER_API_KEY не задан (fallback на Google grounding)")

        return all_ok
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False


async def test_database():
    """Проверка базы данных."""
    print("\n[2/6] Проверка базы данных...")
    try:
        from db import database as db

        # Проверка подключения
        topics = await db.get_used_topics()
        print(f"  ✅ Подключение к БД (найдено {len(topics)} использованных тем)")

        # Проверка структуры
        import aiosqlite
        import config
        async with aiosqlite.connect(config.DB_PATH) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM settings")
            count = (await cursor.fetchone())[0]
        print(f"  ✅ Таблица settings ({count} записей)")

        return True
    except Exception as e:
        print(f"  ❌ Ошибка БД: {e}")
        return False


async def test_gemini():
    """Проверка Gemini AI."""
    print("\n[3/6] Проверка Gemini AI...")
    try:
        from ai.gemini import generate_text

        result = await asyncio.to_thread(
            generate_text,
            "Напиши одно слово: тест",
            temperature=0.0
        )

        if result and len(result) > 0:
            print(f"  ✅ Gemini ответил: '{result[:50]}'")
            return True
        else:
            print(f"  ❌ Gemini вернул пустой ответ")
            return False
    except Exception as e:
        print(f"  ❌ Ошибка Gemini: {e}")
        return False


async def test_serper():
    """Проверка Serper API (опционально)."""
    print("\n[4/6] Проверка Serper API...")
    try:
        import config

        if not config.SERPER_API_KEY:
            print(f"  ⊘ SERPER_API_KEY не задан (пропускаем)")
            return True  # Не критично

        from ai.search import search_news

        news = await search_news("вейп", days=7, num_results=3)

        if news is None:
            print(f"  ⊘ Serper API недоступен (используется fallback)")
            return True
        elif len(news) > 0:
            print(f"  ✅ Serper вернул {len(news)} новостей")
            return True
        else:
            print(f"  ⚠️  Serper вернул 0 результатов (возможно, нет новостей)")
            return True  # Не критично
    except Exception as e:
        print(f"  ⚠️  Ошибка Serper (используется fallback): {e}")
        return True  # Не критично, есть fallback


async def test_telegram():
    """Проверка Telegram API."""
    print("\n[5/6] Проверка Telegram API...")
    try:
        from aiogram import Bot
        import config

        if not config.BOT_TOKEN:
            print(f"  ❌ BOT_TOKEN не задан")
            return False

        bot = Bot(token=config.BOT_TOKEN)
        me = await bot.get_me()
        await bot.session.close()

        print(f"  ✅ Бот подключен: @{me.username} (ID: {me.id})")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка Telegram: {e}")
        return False


async def test_systemd():
    """Проверка systemd служб (только на сервере)."""
    print("\n[6/6] Проверка systemd служб...")
    try:
        import subprocess

        # Проверяем только если systemctl доступен
        result = subprocess.run(
            ["systemctl", "--version"],
            capture_output=True,
            timeout=5
        )

        if result.returncode != 0:
            print(f"  ⊘ systemd недоступен (пропускаем, не на сервере)")
            return True

        # Проверяем статус smoki-bot
        result = subprocess.run(
            ["systemctl", "is-active", "smoki-bot"],
            capture_output=True,
            text=True,
            timeout=5
        )

        status = result.stdout.strip()
        if status == "active":
            print(f"  ✅ smoki-bot.service: active")
            return True
        else:
            print(f"  ⚠️  smoki-bot.service: {status}")
            return True  # Не критично для локального smoke-теста
    except FileNotFoundError:
        print(f"  ⊘ systemctl не найден (пропускаем, не на сервере)")
        return True
    except Exception as e:
        print(f"  ⚠️  Ошибка проверки systemd: {e}")
        return True  # Не критично


async def main():
    """Запуск всех smoke-тестов."""
    print("=" * 70)
    print("SMOKE-ТЕСТИРОВАНИЕ SMOKI BOT")
    print("=" * 70)

    results = {
        "config": await test_config(),
        "database": await test_database(),
        "gemini": await test_gemini(),
        "serper": await test_serper(),
        "telegram": await test_telegram(),
        "systemd": await test_systemd(),
    }

    # Закрываем aiohttp сессию если есть
    try:
        from ai.search import close_session
        await close_session()
    except Exception:
        pass

    print("\n" + "=" * 70)
    print("РЕЗУЛЬТАТЫ SMOKE-ТЕСТОВ")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"  {status_icon} {name}")

    print(f"\nПройдено: {passed}/{total}")

    if passed == total:
        print("\n🎉 Все smoke-тесты прошли успешно!")
        return 0
    else:
        print("\n⚠️  Некоторые тесты провалились. Проверьте конфигурацию.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
