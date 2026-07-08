#!/usr/bin/env python3
"""Ручной health-check живого Gemini AI.

Проверяет реальный API (НЕ моки): инициализация клиента, эхо-текст с подсчётом
токенов, генерация тест-картинки, запись результата в ai_logs.

Запуск: /opt/SMOKI/bot/venv/bin/python scripts/ai_healthcheck.py
Код возврата: 0 — все критичные проверки прошли, 1 — есть провал.
"""
import asyncio
import sys
from pathlib import Path

# корень проекта в путь (скрипт лежит в scripts/)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from ai import gemini  # noqa: E402
from db import database as db  # noqa: E402

OK = "\033[92m✅\033[0m"
FAIL = "\033[91m❌\033[0m"
WARN = "\033[93m⚠️\033[0m"

ECHO_PROMPT = "Ответь ровно одним словом: PONG"
IMAGE_PROMPT = "A simple product photo of an electronic vape device on white background"


def _usage(resp):
    """Достаёт (input_tokens, output_tokens) из usage_metadata, безопасно."""
    um = getattr(resp, "usage_metadata", None)
    if not um:
        return 0, 0
    return (getattr(um, "prompt_token_count", 0) or 0,
            getattr(um, "candidates_token_count", 0) or 0)


def check_client() -> bool:
    print("\n[1/4] Инициализация клиента...")
    try:
        gemini.get_client()
        print(f"  {OK} клиент создан "
              f"(Vertex={config.GOOGLE_GENAI_USE_VERTEXAI}, "
              f"project={config.GOOGLE_CLOUD_PROJECT or '—'}, "
              f"location={config.GOOGLE_CLOUD_LOCATION})")
        return True
    except Exception as e:
        print(f"  {FAIL} не удалось создать клиент: {e}")
        return False


def check_text() -> tuple[bool, int, int]:
    print(f"\n[2/4] Эхо-текст (модель {config.GEMINI_TEXT_MODEL})...")
    try:
        client = gemini.get_client()
        from google.genai import types
        resp = client.models.generate_content(
            model=config.GEMINI_TEXT_MODEL,
            contents=ECHO_PROMPT,
            config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=64),
        )
        text = (resp.text or "").strip()
        inp, out = _usage(resp)
        if text:
            print(f"  {OK} ответ: {text!r}")
            print(f"  {OK} токены: вход={inp}, выход={out}")
            return True, inp, out
        print(f"  {FAIL} пустой ответ (токены вход={inp}, выход={out})")
        return False, inp, out
    except Exception as e:
        print(f"  {FAIL} ошибка генерации текста: {e}")
        return False, 0, 0


def check_image() -> tuple[bool, bool]:
    """Возвращает (успех_вызова, есть_ли_байты)."""
    print(f"\n[3/4] Тест-картинка (модель {config.GEMINI_IMAGE_MODEL})...")
    try:
        data = gemini.generate_image(IMAGE_PROMPT)
        if data:
            print(f"  {OK} картинка получена: {len(data)} байт")
            return True, True
        print(f"  {WARN} вызов прошёл, но байты не вернулись "
              f"(возможно safety-блок промпта — не критично)")
        return True, False
    except Exception as e:
        print(f"  {FAIL} ошибка генерации картинки: {e}")
        return False, False


async def check_log(inp: int, out: int, images: int) -> bool:
    print("\n[4/4] Запись в ai_logs...")
    try:
        await db.init_db()
        await db.log_ai("healthcheck", config.GEMINI_TEXT_MODEL,
                        input_tokens=inp, output_tokens=out, images=images)
        rows = await db.fetch_all(
            "SELECT kind, model, input_tokens, output_tokens, images, created_at "
            "FROM ai_logs WHERE kind='healthcheck' ORDER BY id DESC LIMIT 1"
        ) if hasattr(db, "fetch_all") else None
        if rows:
            r = rows[0]
            print(f"  {OK} запись создана: {dict(r) if hasattr(r, 'keys') else r}")
        else:
            print(f"  {OK} log_ai выполнен (проверка чтения пропущена)")
        return True
    except Exception as e:
        print(f"  {FAIL} ошибка записи в ai_logs: {e}")
        return False


def main() -> int:
    print("=" * 56)
    print(" GEMINI AI HEALTH-CHECK (живой API)")
    print("=" * 56)

    c_ok = check_client()
    if not c_ok:
        print(f"\n{FAIL} Клиент недоступен — остальные проверки пропущены.")
        return 1

    t_ok, inp, out = check_text()
    img_call_ok, img_has_data = check_image()
    log_ok = asyncio.run(check_log(inp, out, 1 if img_has_data else 0))

    print("\n" + "=" * 56)
    print(" ИТОГ")
    print("=" * 56)
    print(f"  клиент .......... {OK if c_ok else FAIL}")
    print(f"  текст+токены .... {OK if t_ok else FAIL}")
    print(f"  картинка (вызов). {OK if img_call_ok else FAIL}"
          f"{' (байты есть)' if img_has_data else ' (без байтов)'}")
    print(f"  запись в лог .... {OK if log_ok else FAIL}")

    # критичные: клиент, текст, вызов картинки, лог. Отсутствие байтов картинки — не фейл.
    critical_ok = c_ok and t_ok and img_call_ok and log_ok
    print("\n" + (f"{OK} ВСЕ КРИТИЧНЫЕ ПРОВЕРКИ ПРОШЛИ"
                  if critical_ok else f"{FAIL} ЕСТЬ ПРОВАЛЫ"))
    return 0 if critical_ok else 1


if __name__ == "__main__":
    sys.exit(main())
