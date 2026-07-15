"""U6.5 — Telethon-userbot: публикация approved story-слотов как Stories.

Отдельный процесс (smoki-userbot.service), НЕ внутри aiogram-бота.
Связь с ботом через общую БД (таблица story_jobs).

Telethon импортируется ЛЕНИВО внутри функций — модуль можно импортировать
и тестировать без установленного telethon (публикация мокается).

Прод-запуск требует (ручной шаг U6.5b):
  - реальные TG_API_ID / TG_API_HASH / TG_USERBOT_PHONE в .env;
  - интерактивную авторизацию сессии (код из SMS) — первый запуск в TTY;
  - буст канала @SMOKTOLK до уровня доступности Stories (иначе ошибка прав).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import config
from db import database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("smoki-userbot")

# Период жизни Story в секундах (24 ч).
_STORY_PERIOD = 86400
# Как часто проверять approved-слоты (сек).
POLL_INTERVAL_SEC = 300


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _publish_story(client: Any, job: dict) -> int | None:
    """Публикует один слот как Story. Возвращает story_msg_id или None.

    Изолировано ради мокабельности в тестах. Telethon-объекты создаются
    здесь лениво, чтобы модуль импортировался без telethon.
    """
    from telethon.tl.functions.stories import SendStoryRequest
    from telethon.tl.types import InputMediaUploadedPhoto

    image_path = job.get("image_path")
    if not image_path:
        logger.warning("Story #%s без image_path — пропуск", job.get("id"))
        return None

    target = job.get("target")
    peer_str = (
        config.STORY_FLOOD_CHANNEL if target == "flood" else config.CHANNEL_ID
    )
    peer = await client.get_input_entity(peer_str)

    uploaded = await client.upload_file(image_path)
    media = InputMediaUploadedPhoto(file=uploaded)
    caption = job.get("caption") or ""

    result = await client(
python3 -c "import ast; ast.parse(open('userbot.py').read())" && echo "userbot.py AST OK"
userbot.py AST OK
cat > deploy/systemd/smoki-userbot.service << 'EOF'
[Unit]
Description=SMOKI userbot (Telethon) — авто-Stories publisher
Documentation=file:/opt/SMOKI/bot/userbot.py
After=network-online.target smoki-bot.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/SMOKI/bot
ExecStart=/opt/SMOKI/bot/venv/bin/python /opt/SMOKI/bot/userbot.py
Restart=always
RestartSec=15
# Первый запуск (авторизация по SMS) выполнить вручную в TTY:
#   /opt/SMOKI/bot/venv/bin/python /opt/SMOKI/bot/userbot.py
# затем: systemctl enable --now smoki-userbot

[Install]
WantedBy=multi-user.target
EOF
echo "unit written"
unit written
cat > tests/test_userbot.py << 'PYEOF'
"""U6.5 — тесты userbot.process_due_stories (публикация мокается)."""
import pytest

import userbot
from db import database


@pytest.mark.asyncio
async def test_publishes_approved_due(tmp_db, monkeypatch):
    await database.init_db()
    jid = await database.add_story_job(
        target="channel", image_path="/tmp/a.png",
        caption="факт", publish_at="2000-01-01T00:00:00+00:00",
    )
    await database.update_story_job(jid, status="approved")

    calls = {}

    async def fake_publish(client, job):
        calls["job_id"] = int(job["id"])
        return 777

    monkeypatch.setattr(userbot, "_publish_story", fake_publish)
    n = await userbot.process_due_stories(client=object())

    assert n == 1
    assert calls["job_id"] == jid
    row = await database.get_story_job(jid)
    assert row["status"] == "published"
    assert row["story_msg_id"] == 777


@pytest.mark.asyncio
async def test_skips_when_no_due(tmp_db, monkeypatch):
    await database.init_db()
    # pending — не approved: publish не должен вызываться
    await database.add_story_job(
        target="channel", image_path="/tmp/a.png", caption="x")

    async def boom(client, job):
        raise AssertionError("не должно вызываться")

    monkeypatch.setattr(userbot, "_publish_story", boom)
    assert await userbot.process_due_stories(client=object()) == 0


@pytest.mark.asyncio
async def test_error_marks_status_error(tmp_db, monkeypatch):
    await database.init_db()
    jid = await database.add_story_job(
        target="channel", image_path="/tmp/a.png",
        caption="x", publish_at="2000-01-01T00:00:00+00:00",
    )
    await database.update_story_job(jid, status="approved")

    async def boom(client, job):
        raise RuntimeError("api down")

    monkeypatch.setattr(userbot, "_publish_story", boom)
    n = await userbot.process_due_stories(client=object())

    assert n == 0
    row = await database.get_story_job(jid)
python3 -c "import ast; ast.parse(open('tests/test_userbot.py').read())" && echo "test AST OK"
test AST OK
grep -n "bandit" .github/workflows/ci.yml
52:      - name: Install bandit
53:        run: pip install bandit==1.9.4
54:      - name: Run bandit
55:        run: bandit -r . -x venv,data,__pycache__ -ll
python3 << 'PYEOF'
p = "docs/SPEC.md"
s = open(p).read()
anchor = "### U6.6 Конфиг и зависимости"
assert anchor in s
done = (
    "- [x] Публикация userbot РЕАЛИЗОВАНА-КОД (feature/u6-5-userbot-publish): "
    "`userbot.py` — отдельный процесс, Telethon импортируется ЛЕНИВО внутри "
    "функций (модуль тестируется без установленного telethon). "
    "`process_due_stories(client)` читает `db.get_due_approved_story_jobs(now)`, "
    "`_publish_story` шлёт `SendStoryRequest(peer, InputMediaUploadedPhoto, "
    "period=86400)` (peer = CHANNEL_ID для channel / STORY_FLOOD_CHANNEL для "
    "flood), затем `update_story_job(status='published', story_msg_id=...)`; "
    "ошибка отдельного слота → `status='error'`, цикл не падает. "
    "`main()` — цикл с POLL_INTERVAL_SEC=300. Юнит "
    "`deploy/systemd/smoki-userbot.service` (Restart=always). Тест "
    "`tests/test_userbot.py` (мок публикации: approved-due→published, "
    "пропуск pending, ошибка→error, `_extract_story_id`).\n"
    "- [ ] U6.5b РУЧНОЙ ПРОД-ШАГ (ждёт API от владельца): реальные "
    "`TG_API_ID`/`TG_API_HASH`/`TG_USERBOT_PHONE` в `.env`; интерактивная "
    "авторизация сессии (SMS-код, первый запуск в TTY); буст канала "
    "@SMOKTOLK до уровня Stories; `pip install telethon==1.44.0` в venv; "
    "`systemctl enable --now smoki-userbot`. БЕЗ буста SendStoryRequest "
    "вернёт ошибку прав — прод-запуск только после буста.\n\n"
)
s = s.replace(anchor, done + anchor, 1)
open(p, "w").write(s)
print("SPEC patched")
