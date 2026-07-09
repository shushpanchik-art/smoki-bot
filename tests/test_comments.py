import pytest

from services import comments

pytestmark = pytest.mark.asyncio


class FakeBot:
    def __init__(self):
        self.deleted = []
        self.sent = []

    async def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text, kw))


def _patch_db(monkeypatch, rows):
    updates = []

    async def fake_get_new_comments(limit=50):
        return list(rows)

    async def fake_update_comment(comment_id, **fields):
        updates.append((comment_id, fields))

    async def fake_log_ai(*a, **k):
        return None

    monkeypatch.setattr(comments.db, "get_new_comments", fake_get_new_comments)
    monkeypatch.setattr(comments.db, "update_comment", fake_update_comment)
    monkeypatch.setattr(comments.db, "log_ai", fake_log_ai)
    return updates


# ---------- _classify ----------
async def test_classify_whitelist(monkeypatch):
    def fake_gen(prompt, **kw):
        return "reklama"
    monkeypatch.setattr(comments.gemini, "generate_text", fake_gen)
    monkeypatch.setattr(comments.db, "log_ai", _noop)
    cat = await comments._classify("купи вейп дёшево")
    assert cat == "reklama"


async def test_classify_dirty_output_normalized(monkeypatch):
    def fake_gen(prompt, **kw):
        return "  Question.\nещё текст"
    monkeypatch.setattr(comments.gemini, "generate_text", fake_gen)
    monkeypatch.setattr(comments.db, "log_ai", _noop)
    cat = await comments._classify("а какой вкус лучше?")
    assert cat == "question"


async def test_classify_unknown_fallback_neutral(monkeypatch):
    def fake_gen(prompt, **kw):
        return "абракадабра"
    monkeypatch.setattr(comments.gemini, "generate_text", fake_gen)
    monkeypatch.setattr(comments.db, "log_ai", _noop)
    cat = await comments._classify("что-то")
    assert cat == "neutral"


async def test_classify_empty_fallback_neutral(monkeypatch):
    def fake_gen(prompt, **kw):
        return "   "
    monkeypatch.setattr(comments.gemini, "generate_text", fake_gen)
    monkeypatch.setattr(comments.db, "log_ai", _noop)
    cat = await comments._classify("")
    assert cat == "neutral"


async def _noop(*a, **k):
    return None


# ---------- process_new_comments ----------
async def test_process_deletes_reklama(monkeypatch):
    rows = [{"id": 1, "chat_id": -100, "message_id": 5, "text": "спам"}]
    updates = _patch_db(monkeypatch, rows)

    async def fake_classify(text):
        return "reklama"
    monkeypatch.setattr(comments, "_classify", fake_classify)

    bot = FakeBot()
    stats = await comments.process_new_comments(bot)
    assert stats["deleted"] == 1
    assert bot.deleted == [(-100, 5)]
    assert not bot.sent
    assert updates[0][1]["status"] == "deleted"


async def test_process_replies_question(monkeypatch):
    rows = [{"id": 2, "chat_id": -100, "message_id": 6, "text": "какой вкус?"}]
    updates = _patch_db(monkeypatch, rows)

    async def fake_classify(text):
        return "question"

    async def fake_reply(text, category):
        return "Отличный вопрос!"
    monkeypatch.setattr(comments, "_classify", fake_classify)
    monkeypatch.setattr(comments, "_reply", fake_reply)

    bot = FakeBot()
    stats = await comments.process_new_comments(bot)
    assert stats["replied"] == 1
    assert bot.sent[0][0] == -100
    assert bot.sent[0][1] == "Отличный вопрос!"
    assert bot.sent[0][2]["reply_to_message_id"] == 6
    assert updates[0][1]["status"] == "replied"
    assert updates[0][1]["bot_reply"] == "Отличный вопрос!"


async def test_process_telegram_error_marks_error(monkeypatch):
    rows = [{"id": 3, "chat_id": -100, "message_id": 7, "text": "мусор"}]
    updates = _patch_db(monkeypatch, rows)

    async def fake_classify(text):
        return "toxic"
    monkeypatch.setattr(comments, "_classify", fake_classify)

    class BadBot(FakeBot):
        async def delete_message(self, chat_id, message_id):
            raise RuntimeError("no rights")

    stats = await comments.process_new_comments(BadBot())
    assert stats["errors"] == 1
    assert updates[0][1]["status"] == "error"


async def test_process_classify_error_marks_error(monkeypatch):
    rows = [{"id": 4, "chat_id": -100, "message_id": 8, "text": "x"}]
    updates = _patch_db(monkeypatch, rows)

    async def bad_classify(text):
        raise RuntimeError("ai down")
    monkeypatch.setattr(comments, "_classify", bad_classify)

    stats = await comments.process_new_comments(FakeBot())
    assert stats["errors"] == 1
    assert updates[0][1]["status"] == "error"


async def test_process_empty(monkeypatch):
    _patch_db(monkeypatch, [])
    stats = await comments.process_new_comments(FakeBot())
    assert stats == {"processed": 0, "deleted": 0, "replied": 0, "errors": 0}
