import asyncio
import scheduler
import config


def test_generation_failure_alerts_admin(monkeypatch):
    sent = {}

    class FakeBot:
        async def send_message(self, chat_id, text, **kw):
            sent["chat_id"] = chat_id
            sent["text"] = text

    async def boom(**kwargs):
        raise RuntimeError("BILLING_DISABLED")

    monkeypatch.setattr(scheduler, "_bot", FakeBot())
    monkeypatch.setattr(scheduler.content, "generate_article", boom)

    asyncio.run(scheduler._generate_and_moderate("short", "тест"))

    assert sent.get("chat_id") == config.ADMIN_CHAT_ID, "алерт не ушёл админу"
    assert "УПАЛА" in sent.get("text", ""), "текст алерта не тот"
