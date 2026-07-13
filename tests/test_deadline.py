"""Дедлайн-джоб публикует ВСЕ зависшие статьи дня (tmp_db)."""
import pytest

import scheduler


class _FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


@pytest.mark.asyncio
async def test_deadline_publishes_all_stuck(tmp_db, monkeypatch):
    from db import database as db
    await db.init_db()

    t1 = await db.add_topic("d1", category="article")
    t2 = await db.add_topic("d2", category="article")
    a1 = await db.add_article(t1, body="body1")
    a2 = await db.add_article(t2, body="body2")

    published: list[int] = []

    async def fake_publish(bot, aid):  # noqa: ANN001, ANN202
        published.append(aid)
        return {"ok": True}

    monkeypatch.setattr(scheduler.publisher, "publish_article", fake_publish)

    bot = _FakeBot()
    scheduler._bot = bot  # noqa: SLF001

    await scheduler._job_deadline()  # noqa: SLF001

    assert sorted(published) == sorted([a1, a2])
    assert bot.sent, "админ должен получить сводку"
    assert f"#{a1}" in bot.sent[0][1]
    assert f"#{a2}" in bot.sent[0][1]


@pytest.mark.asyncio
async def test_deadline_no_stuck(tmp_db, monkeypatch):
    from db import database as db
    await db.init_db()

    called: list[int] = []

    async def fake_publish(bot, aid):  # noqa: ANN001, ANN202
        called.append(aid)
        return {"ok": True}

    monkeypatch.setattr(scheduler.publisher, "publish_article", fake_publish)

    bot = _FakeBot()
    scheduler._bot = bot  # noqa: SLF001

    await scheduler._job_deadline()  # noqa: SLF001

    assert called == []
    assert bot.sent == []
