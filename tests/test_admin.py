"""Тесты helper-функций handlers/admin.py (покрытие чистой логики)."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import config
from handlers import admin


def test_is_admin_id_matches(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 777)
    assert admin._is_admin_id(777) is True
    assert admin._is_admin_id(1) is False


def test_is_admin_id_zero_disabled(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 0)
    assert admin._is_admin_id(0) is False
    assert admin._is_admin_id(123) is False


def test_is_admin_message(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", 555)
    msg_ok = SimpleNamespace(from_user=SimpleNamespace(id=555))
    msg_bad = SimpleNamespace(from_user=SimpleNamespace(id=1))
    msg_none = SimpleNamespace(from_user=None)
    assert admin._is_admin(msg_ok) is True
    assert admin._is_admin(msg_bad) is False
    assert admin._is_admin(msg_none) is False


def test_cb_arg_extracts_int():
    cq = SimpleNamespace(data="approve:42")
    assert admin._cb_arg(cq) == 42


def test_cb_arg_none_raises():
    cq = SimpleNamespace(data=None)
    with pytest.raises((ValueError, IndexError)):
        admin._cb_arg(cq)


def test_bot_returns_bot():
    fake_bot = object()
    cq = SimpleNamespace(bot=fake_bot)
    assert admin._bot(cq) is fake_bot


def test_bot_none_asserts():
    cq = SimpleNamespace(bot=None)
    with pytest.raises(AssertionError):
        admin._bot(cq)


@pytest.mark.parametrize(
    "text,expected",
    [
        (None, True),
        ("", True),
        ("-", True),
        ("—", True),
        ("нет", True),
        (" SKIP ", True),
        ("пропустить", True),
        ("нормальный фидбек", False),
        ("да", False),
    ],
)
def test_is_skip(text, expected):
    assert admin._is_skip(text) is expected


def test_kb_builds_markup():
    kb = admin._kb(99)
    # InlineKeyboardMarkup имеет .inline_keyboard (список рядов)
    assert hasattr(kb, "inline_keyboard")
    flat = [btn for row in kb.inline_keyboard for btn in row]
    assert any("99" in (b.callback_data or "") for b in flat)


async def test_clear_markup_success():
    msg = MagicMock()
    msg.edit_reply_markup = AsyncMock()
    cq = SimpleNamespace(message=msg)
    await admin._clear_markup(cq)
    msg.edit_reply_markup.assert_awaited_once()


async def test_clear_markup_no_message():
    cq = SimpleNamespace(message=None)
    await admin._clear_markup(cq)  # не должно падать


async def test_clear_markup_swallows_error():
    msg = MagicMock()
    msg.edit_reply_markup = AsyncMock(side_effect=Exception("boom"))
    cq = SimpleNamespace(message=msg)
    await admin._clear_markup(cq)  # исключение проглатывается
    msg.edit_reply_markup.assert_awaited_once()


# --- cb_adm_backup: запуск бэкапа + чтение отчёта из journald ---

class _FakeProc:
    """Мок asyncio-процесса: заданные stdout и returncode."""
    def __init__(self, out: bytes, rc: int):
        self._out = out
        self.returncode = rc

    async def communicate(self):
        return self._out, b""


async def test_cb_adm_backup_success(monkeypatch):
    """rc=0: бот читает journald и присылает отчёт с итогом бэкапа."""
    calls = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        # первый вызов — systemctl start (rc=0),
        # второй — journalctl (отдаёт лог со stats/backup ok)
        if args[0] == "systemctl":
            return _FakeProc(b"", 0)
        return _FakeProc(b"backup ok: smoki-20240101.tar.gz\nstats: files=3, total_size=1024B\n", 0)

    monkeypatch.setattr(admin.asyncio, "create_subprocess_exec", fake_exec)

    async def ok_guard(cq):
        return True
    monkeypatch.setattr(admin, "_cb_guard", ok_guard)

    msg = MagicMock()
    msg.answer = AsyncMock()

    async def fake_msg(cq):
        return msg
    monkeypatch.setattr(admin, "_cb_msg", fake_msg)

    cq = MagicMock()
    cq.answer = AsyncMock()

    await admin.cb_adm_backup(cq)

    msg.answer.assert_awaited()
    sent = msg.answer.await_args.args[0]
    assert "Бэкап выполнен" in sent
    assert "backup ok" in sent or "stats" in sent
    # systemctl start вызывался
    assert any(c[0] == "systemctl" for c in calls)
    # journalctl тоже вызывался (чтение отчёта)
    assert any(c[0] == "journalctl" for c in calls)


async def test_cb_adm_backup_error(monkeypatch):
    """rc!=0: бот присылает сообщение об ошибке с кодом возврата."""
    async def fake_exec(*args, **kwargs):
        return _FakeProc(b"unit failed\n", 1)
    monkeypatch.setattr(admin.asyncio, "create_subprocess_exec", fake_exec)

    async def ok_guard(cq):
        return True
    monkeypatch.setattr(admin, "_cb_guard", ok_guard)

    msg = MagicMock()
    msg.answer = AsyncMock()

    async def fake_msg(cq):
        return msg
    monkeypatch.setattr(admin, "_cb_msg", fake_msg)

    cq = MagicMock()
    cq.answer = AsyncMock()

    await admin.cb_adm_backup(cq)

    msg.answer.assert_awaited()
    sent = msg.answer.await_args.args[0]
    assert "ошибк" in sent.lower()
    assert "rc=1" in sent


async def test_cb_adm_backup_denied(monkeypatch):
    """Не-админ: guard возвращает False, бэкап не запускается."""
    started = []

    async def fake_exec(*args, **kwargs):
        started.append(args)
        return _FakeProc(b"", 0)
    monkeypatch.setattr(admin.asyncio, "create_subprocess_exec", fake_exec)

    async def deny_guard(cq):
        return False
    monkeypatch.setattr(admin, "_cb_guard", deny_guard)

    cq = MagicMock()
    cq.answer = AsyncMock()

    await admin.cb_adm_backup(cq)

    assert started == []  # процесс не запускался
