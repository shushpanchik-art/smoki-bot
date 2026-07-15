"""U6.x: ручная команда /story — генерит channel-слот и шлёт на модерацию."""
from unittest.mock import AsyncMock, patch

import pytest

from db import database as db
from handlers import admin


class _Msg:
    def __init__(self, uid: int):
        self.from_user = type("U", (), {"id": uid})()
        self.answer = AsyncMock()


@pytest.mark.asyncio
async def test_cmd_story_ok(tmp_db, monkeypatch):
    await db.init_db()
    monkeypatch.setattr(admin.config, "ADMIN_CHAT_ID", 111)
    bot = AsyncMock()

    with patch.object(admin.stories, "generate_channel_slot",
                      new=AsyncMock(return_value=42)) as gen, \
         patch.object(admin, "send_story_for_moderation",
                      new=AsyncMock()) as send:
        await admin.cmd_story(_Msg(111), bot)

    gen.assert_awaited_once()
    send.assert_awaited_once_with(bot, 42)


@pytest.mark.asyncio
async def test_cmd_story_not_admin(tmp_db, monkeypatch):
    await db.init_db()
    monkeypatch.setattr(admin.config, "ADMIN_CHAT_ID", 111)
    bot = AsyncMock()
    with patch.object(admin.stories, "generate_channel_slot",
                      new=AsyncMock()) as gen:
        await admin.cmd_story(_Msg(999), bot)
    gen.assert_not_awaited()


@pytest.mark.asyncio
async def test_cmd_story_no_slot(tmp_db, monkeypatch):
    await db.init_db()
    monkeypatch.setattr(admin.config, "ADMIN_CHAT_ID", 111)
    bot = AsyncMock()
    msg = _Msg(111)
    with patch.object(admin.stories, "generate_channel_slot",
                      new=AsyncMock(return_value=None)), \
         patch.object(admin, "send_story_for_moderation",
                      new=AsyncMock()) as send:
        await admin.cmd_story(msg, bot)
    send.assert_not_awaited()
