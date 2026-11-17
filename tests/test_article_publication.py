import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiosqlite
import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import SendMessage, SendPhoto

import config
from db import database as db
from services import publisher

CAPTION = "Opening"
CONTINUATION = "Continuation " * 120


@pytest.fixture
def fake_bot(monkeypatch):
    monkeypatch.setattr(config, "CHANNEL_ID", "@test_channel")
    monkeypatch.setattr(publisher.webhooks, "send_webhook", AsyncMock())
    return SimpleNamespace(
        send_photo=AsyncMock(return_value=SimpleNamespace(message_id=384)),
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=385)),
    )


async def add_article(tmp_path, *, photo=True):
    await db.init_db()
    topic = await db.add_topic("Test topic", "test")
    image = tmp_path / "image.png"
    image.write_bytes(b"test fixture")
    article = await db.add_article(
        topic, f"{CAPTION}\n\n{CONTINUATION.strip()}", str(image) if photo else None,
    )
    return article, topic


async def publication_parts(tmp_db, article):
    async with aiosqlite.connect(tmp_db) as conn:
        rows = await conn.execute_fetchall(
            "SELECT state, message_id FROM article_publication_parts "
            "WHERE article_id = ? ORDER BY position", (article,),
        )
        return list(rows)


@pytest.mark.asyncio
async def test_complete_and_repeat(tmp_db, tmp_path, fake_bot):
    article, topic = await add_article(tmp_path)
    first = await publisher.publish_article(fake_bot, article)
    second = await publisher.publish_article(fake_bot, article)

    assert first == second == {"ok": True, "message_id": 384}
    fake_bot.send_photo.assert_awaited_once()
    assert fake_bot.send_photo.await_args.kwargs["caption"] == CAPTION
    fake_bot.send_message.assert_awaited_once_with(
        "@test_channel", CONTINUATION.strip(), parse_mode="HTML",
    )
    publisher.webhooks.send_webhook.assert_awaited_once()
    row = await db.get_article(article)
    assert row["status"] == "published"
    assert row["message_id"] == 384
    assert row["published_at"]
    assert await publication_parts(tmp_db, article) == [
        ("confirmed", 384), ("confirmed", 385),
    ]
    async with aiosqlite.connect(tmp_db) as conn:
        assert await conn.execute_fetchall(
            "SELECT status FROM published_topics WHERE id = ?", (topic,),
        ) == [("published",)]


@pytest.mark.asyncio
async def test_text_rejection_preserves_photo_and_resumes_after_restart(tmp_db, tmp_path, fake_bot):
    article, _ = await add_article(tmp_path)
    fake_bot.send_message.side_effect = TelegramBadRequest(
        SendMessage(chat_id="@test_channel", text=CONTINUATION), "rejected",
    )

    assert not (await publisher.publish_article(fake_bot, article))["ok"]
    row = await db.get_article(article)
    assert row["status"] == "pending"
    assert row["message_id"] == 384
    assert row["published_at"] is None
    assert await publication_parts(tmp_db, article) == [
        ("confirmed", 384), ("pending", None),
    ]
    publisher.webhooks.send_webhook.assert_not_awaited()

    await db.init_db()  # Startup against the same file.
    fake_bot.send_message.side_effect = None
    assert await publisher.publish_article(fake_bot, article) == {"ok": True, "message_id": 384}
    fake_bot.send_photo.assert_awaited_once()
    assert fake_bot.send_message.await_count == 2
    assert await publication_parts(tmp_db, article) == [
        ("confirmed", 384), ("confirmed", 385),
    ]


@pytest.mark.asyncio
async def test_photo_rejection_cannot_publish_text_alone(tmp_db, tmp_path, fake_bot):
    article, _ = await add_article(tmp_path)
    fake_bot.send_photo.side_effect = TelegramBadRequest(
        SendPhoto(chat_id="@test_channel", photo="fixture"), "rejected",
    )

    assert not (await publisher.publish_article(fake_bot, article))["ok"]
    assert (await db.get_article(article))["status"] == "pending"
    fake_bot.send_message.assert_not_awaited()
    publisher.webhooks.send_webhook.assert_not_awaited()
    assert await publication_parts(tmp_db, article) == [("pending", None), ("pending", None)]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [
    TimeoutError(),
    TelegramNetworkError(SendMessage(chat_id="@test_channel", text="test"), "connection reset"),
])
async def test_unknown_delivery_stops_retry_across_restart(tmp_db, tmp_path, fake_bot, failure):
    article, _ = await add_article(tmp_path)
    fake_bot.send_message.side_effect = failure

    assert not (await publisher.publish_article(fake_bot, article))["ok"]
    await db.init_db()
    fake_bot.send_message.side_effect = None
    assert not (await publisher.publish_article(fake_bot, article))["ok"]
    fake_bot.send_photo.assert_awaited_once()
    fake_bot.send_message.assert_awaited_once()
    assert (await db.get_article(article))["status"] == "pending"
    assert await publication_parts(tmp_db, article) == [
        ("confirmed", 384), ("uncertain", None),
    ]


@pytest.mark.asyncio
async def test_concurrent_publishers_send_each_part_once(tmp_db, tmp_path, fake_bot):
    article, _ = await add_article(tmp_path)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def send_photo(*args, **kwargs):
        entered.set()
        await release.wait()
        return SimpleNamespace(message_id=384)

    fake_bot.send_photo.side_effect = send_photo
    first = asyncio.create_task(publisher.publish_article(fake_bot, article))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        second = await asyncio.wait_for(publisher.publish_article(fake_bot, article), timeout=2)
        assert not second["ok"]
    finally:
        release.set()
        completed = await first
    assert completed["ok"]
    fake_bot.send_photo.assert_awaited_once()
    fake_bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancelled_request_stays_uncertain(tmp_db, tmp_path, fake_bot):
    article, _ = await add_article(tmp_path)
    fake_bot.send_photo.side_effect = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await publisher.publish_article(fake_bot, article)
    await db.init_db()
    fake_bot.send_photo.side_effect = None
    assert not (await publisher.publish_article(fake_bot, article))["ok"]
    fake_bot.send_photo.assert_awaited_once()
    fake_bot.send_message.assert_not_awaited()
    assert await publication_parts(tmp_db, article) == [("uncertain", None), ("pending", None)]


@pytest.mark.asyncio
async def test_missing_known_image_cannot_silently_become_text(tmp_db, tmp_path, fake_bot):
    article, _ = await add_article(tmp_path)
    (tmp_path / "image.png").unlink()

    assert not (await publisher.publish_article(fake_bot, article))["ok"]
    fake_bot.send_photo.assert_not_awaited()
    fake_bot.send_message.assert_not_awaited()
    assert (await db.get_article(article))["status"] == "pending"


@pytest.mark.asyncio
async def test_legacy_rows_survive_repeated_additive_migration(tmp_db, tmp_path, fake_bot):
    article, _ = await add_article(tmp_path)
    legacy = await db.add_article(None, "Legacy article")
    await db.update_article(legacy, status="published", message_id=107, published_at="2026-01-01")
    invalid_legacy = await db.add_article(None, "Unverified legacy article")
    await db.update_article(invalid_legacy, status="published")
    async with aiosqlite.connect(tmp_db) as conn:
        await conn.execute("DROP TABLE IF EXISTS article_publication_parts")
        await conn.commit()

    await db.init_db()
    await db.init_db()

    assert await publisher.publish_article(fake_bot, legacy) == {"ok": True, "message_id": 107}
    assert (await db.get_article(legacy))["published_at"] == "2026-01-01"
    assert not (await publisher.publish_article(fake_bot, invalid_legacy))["ok"]
    fake_bot.send_photo.assert_not_awaited()
    fake_bot.send_message.assert_not_awaited()
    assert (await publisher.publish_article(fake_bot, article))["ok"]


@pytest.mark.asyncio
async def test_text_only_article_records_confirmed_id(tmp_db, tmp_path, fake_bot):
    article, _ = await add_article(tmp_path, photo=False)

    assert await publisher.publish_article(fake_bot, article) == {"ok": True, "message_id": 385}
    fake_bot.send_photo.assert_not_awaited()
    assert await publication_parts(tmp_db, article) == [("confirmed", 385)]


@pytest.mark.asyncio
async def test_failed_ack_write_blocks_resend_and_history_can_reconcile(
    tmp_db, tmp_path, fake_bot, monkeypatch, caplog,
):
    article, _ = await add_article(tmp_path, photo=False)

    async def fail_write(*args):
        raise aiosqlite.OperationalError("simulated disk failure")

    from db import article_publication

    with monkeypatch.context() as patch:
        patch.setattr(article_publication, "resolve", fail_write)
        assert not (await publisher.publish_article(fake_bot, article))["ok"]
    assert "message_id=385" in caplog.text
    assert await publication_parts(tmp_db, article) == [("uncertain", None)]
    assert not (await publisher.publish_article(fake_bot, article))["ok"]

    # An operator confirmed the exact message in channel history.
    await article_publication.resolve(article, 1, 385)
    assert await publisher.publish_article(fake_bot, article) == {"ok": True, "message_id": 385}
    fake_bot.send_message.assert_awaited_once()
    assert await publication_parts(tmp_db, article) == [("confirmed", 385)]


@pytest.mark.asyncio
async def test_zero_message_id_requires_reconciliation(tmp_db, tmp_path, fake_bot):
    article, _ = await add_article(tmp_path, photo=False)
    fake_bot.send_message.return_value = SimpleNamespace(message_id=0)

    assert not (await publisher.publish_article(fake_bot, article))["ok"]
    assert not (await publisher.publish_article(fake_bot, article))["ok"]
    fake_bot.send_message.assert_awaited_once()
    assert await publication_parts(tmp_db, article) == [("uncertain", None)]
