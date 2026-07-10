import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import config
from db import database as db
from services import content, publisher
from ai import prompts

logger = logging.getLogger(__name__)
router = Router(name="admin")

SKIP = {"-", "—", "нет", "no", "skip", "пропустить"}


class ModerationStates(StatesGroup):
    waiting_publish_fb = State()
    waiting_regen_fb = State()
    waiting_reject_fb = State()


def _is_admin_id(uid: int) -> bool:
    return bool(config.ADMIN_CHAT_ID) and uid == config.ADMIN_CHAT_ID


def _is_admin(message: Message) -> bool:
    return message.from_user is not None and _is_admin_id(message.from_user.id)


def _cb_arg(cq: CallbackQuery) -> int:
    """Извлечь int-аргумент после ':' из callback_data."""
    return int((cq.data or "").split(":")[1])


def _bot(cq: CallbackQuery) -> Bot:
    """Достать Bot из callback (mypy-safe)."""
    assert cq.bot is not None
    return cq.bot


def _is_skip(text: str | None) -> bool:
    return not text or text.strip().lower() in SKIP


async def _clear_markup(cq: CallbackQuery) -> None:
    msg = cq.message
    if msg is not None and hasattr(msg, "edit_reply_markup"):
        try:
            await msg.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.debug("edit_reply_markup failed", exc_info=True)


def _kb(article_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"pub:{article_id}"),
            InlineKeyboardButton(text="🔄 Заново", callback_data=f"regen:{article_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej:{article_id}"),
        ],
        [
            InlineKeyboardButton(text="⛔ Отмена", callback_data=f"cancel:{article_id}"),
        ],
    ])


CAPTION_LIMIT = 1024


async def send_for_moderation(bot: Bot, article_id: int):
    """Отправить черновик статьи админу с кнопками модерации."""
    art = await db.get_article(article_id)
    if not art:
        logger.warning("send_for_moderation: статья #%s не найдена", article_id)
        return
    body = art["body"] or ""
    image_path = art.get("image_path")
    header = f"📝 <b>Черновик #{article_id}</b>\n\n"
    kb = _kb(article_id)

    has_img = bool(image_path) and Path(str(image_path)).exists()
    full = header + body

    async def _send_text_with_kb():
        parts = publisher._split(body, 4000)
        for i, part in enumerate(parts):
            prefix = header if i == 0 else ""
            last = i == len(parts) - 1
            await bot.send_message(
                config.ADMIN_CHAT_ID, prefix + part,
                reply_markup=kb if last else None,
            )

    if has_img and len(full) <= CAPTION_LIMIT:
        try:
            await bot.send_photo(
                config.ADMIN_CHAT_ID, FSInputFile(str(image_path)),
                caption=full, reply_markup=kb,
            )
        except Exception:
            logger.exception("send_for_moderation: фото+caption #%s", article_id)
            await bot.send_message(config.ADMIN_CHAT_ID, full, reply_markup=kb)
    else:
        if has_img:
            try:
                await bot.send_photo(
                    config.ADMIN_CHAT_ID, FSInputFile(str(image_path)),
                )
            except Exception:
                logger.exception("send_for_moderation: фото #%s", article_id)
        await _send_text_with_kb()


# ---------- команды ----------
@router.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(
        f"chat_id этого чата: <code>{message.chat.id}</code>\n"
        f"тип чата: {message.chat.type}\n"
        f"твой user_id: <code>{message.from_user.id if message.from_user else '?'}</code>"
    )


@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.chat.type != "private":
        return
    if not _is_admin(message):
        await message.answer(
            "Это служебный бот автоведения канала SMOKI.\n"
            f"Твой user_id: <code>{message.from_user.id if message.from_user else '?'}</code>\n"
            "Если ты администратор — впиши этот id в ADMIN_CHAT_ID (.env)."
        )
        return
    await message.answer(
        "👋 SMOKI content bot готов.\n\n"
        "Команды:\n"
        "/generate — черновик поста (обычный)\n"
        "/generate morning — утренний формат (факты, тек. длина)\n"
        "/generate evening — вечерний лонг-рид (тек. длина)\n"
        "/setlen — показать/изменить желаемую длину постов\n"
        "/id — показать id чата"
    )


@router.message(Command("generate"))
async def cmd_generate(message: Message, bot: Bot):
    if not _is_admin(message):
        return
    parts = (message.text or "").split()
    fmt = parts[1].lower() if len(parts) > 1 else ""
    length_hint = None
    if fmt == "morning":
        n = int(await db.get_setting(
            "morning_facts", str(config.MORNING_LEN_DEFAULT))
            or config.MORNING_LEN_DEFAULT)
        length_hint = prompts.facts_rules(n)
        await message.answer(f"⏳ Утренний формат ({n} факт(ов))…")
    elif fmt == "evening":
        w = int(await db.get_setting(
            "evening_words", str(config.EVENING_WORDS_DEFAULT))
            or config.EVENING_WORDS_DEFAULT)
        length_hint = prompts.words_rule(w)
        await message.answer(f"⏳ Вечерний лонг-рид (~{w} слов)…")
    else:
        await message.answer("⏳ Генерирую черновик, подожди ~30-60 сек…")
    try:
        res = await content.generate_article(length_hint=length_hint)
    except Exception as e:
        logger.exception("generate")
        await message.answer(f"❌ Ошибка генерации: {e}")
        return
    if not res.get("ok"):
        await message.answer(f"🚫 Не прошло цензуру:\n{res.get('reason','')[:500]}")
        return
    await send_for_moderation(bot, res["article_id"])


# ---------- модерация: кнопка → спросить фидбэк (FSM) ----------
@router.message(Command("setlen"))
async def cmd_setlen(message: Message):
    """Настройка длины: /setlen morning 2  |  /setlen evening 400"""
    if not _is_admin(message):
        return
    parts = (message.text or "").split()
    cur_m = await db.get_setting("morning_facts", str(config.MORNING_LEN_DEFAULT))
    cur_e = await db.get_setting("evening_words", str(config.EVENING_WORDS_DEFAULT))
    if len(parts) != 3 or parts[1] not in ("morning", "evening"):
        await message.answer(
            "Текущие настройки:\n"
            f"• утро (фактов): <b>{cur_m}</b>\n"
            f"• вечер (слов): <b>{cur_e}</b>\n\n"
            "Изменить:\n"
            "<code>/setlen morning 2</code> (1-3)\n"
            "<code>/setlen evening 400</code> (200-500)",
            parse_mode="HTML",
        )
        return
    try:
        val = int(parts[2])
    except ValueError:
        await message.answer("Число не распознано.")
        return
    if parts[1] == "morning":
        val = max(1, min(3, val))
        await db.set_setting("morning_facts", str(val))
        await message.answer(f"✅ Утро: {val} факта(ов).")
    else:
        val = max(200, min(500, val))
        await db.set_setting("evening_words", str(val))
        await message.answer(f"✅ Вечер: {val} слов.")


@router.callback_query(F.data.startswith("pub:"))
async def cb_publish(cq: CallbackQuery, state: FSMContext):
    if not _is_admin_id(cq.from_user.id):
        await cq.answer("Не для тебя", show_alert=True)
        return
    aid = _cb_arg(cq)
    await state.set_state(ModerationStates.waiting_publish_fb)
    await state.update_data(article_id=aid)
    await cq.answer()
    await _clear_markup(cq)
    await _bot(cq).send_message(
        config.ADMIN_CHAT_ID,
        f"✍️ Что понравилось в статье #{aid}? "
        "Напиши — я запомню стиль. Или отправь <code>-</code>, чтобы просто опубликовать.",
    )


@router.callback_query(F.data.startswith("regen:"))
async def cb_regen(cq: CallbackQuery, state: FSMContext):
    if not _is_admin_id(cq.from_user.id):
        await cq.answer("Не для тебя", show_alert=True)
        return
    aid = _cb_arg(cq)
    old = await db.get_article(aid)
    regen = (old.get("regen_count") or 0) if old else 0
    if regen >= config.MAX_REGEN:
        await cq.answer(f"Лимит перегенераций ({config.MAX_REGEN}) исчерпан", show_alert=True)
        return
    await state.set_state(ModerationStates.waiting_regen_fb)
    await state.update_data(article_id=aid, regen_count=regen)
    await cq.answer()
    await _clear_markup(cq)
    await _bot(cq).send_message(
        config.ADMIN_CHAT_ID,
        f"✍️ Что улучшить в статье #{aid}? "
        "Опиши правки — учту при генерации. Или <code>-</code> для обычного регена.",
    )


@router.callback_query(F.data.startswith("rej:"))
async def cb_reject(cq: CallbackQuery, state: FSMContext):
    if not _is_admin_id(cq.from_user.id):
        await cq.answer("Не для тебя", show_alert=True)
        return
    aid = _cb_arg(cq)
    await state.set_state(ModerationStates.waiting_reject_fb)
    await state.update_data(article_id=aid)
    await cq.answer()
    await _clear_markup(cq)
    await _bot(cq).send_message(
        config.ADMIN_CHAT_ID,
        f"✍️ Что не так со статьёй #{aid}? "
        "Опиши — добавлю в правила цензуры и сгенерирую заново. "
        "Или <code>-</code>, чтобы просто перегенерировать.",
    )


@router.callback_query(F.data.startswith("cancel:"))
async def cb_cancel(cq: CallbackQuery, state: FSMContext):
    """Админ передумал: закрыть модерацию без публикации и без регенерации."""
    if not _is_admin_id(cq.from_user.id):
        await cq.answer("Не для тебя", show_alert=True)
        return
    aid = _cb_arg(cq)
    await state.clear()
    await db.update_article(aid, status="cancelled")
    await cq.answer("Отменено")
    await _clear_markup(cq)
    await _bot(cq).send_message(
        config.ADMIN_CHAT_ID,
        f"⛔ Статья #{aid} снята с публикации. Ничего не отправлено.",
    )


# ---------- модерация: приём текстового фидбэка ----------
@router.message(ModerationStates.waiting_publish_fb)
async def fb_publish(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message):
        return
    data = await state.get_data()
    aid = int(data.get("article_id") or 0)
    await state.clear()
    fb = message.text or ""
    if not _is_skip(fb):
        await db.update_article(aid, admin_feedback=fb)
        await db.append_setting("liked_feedback", fb)
    res = await publisher.publish_article(bot, aid)
    if res["ok"]:
        await message.answer(f"✅ Статья #{aid} опубликована (msg {res['message_id']}).")
    else:
        await message.answer(f"❌ Ошибка публикации #{aid}: {res['error']}")


@router.message(ModerationStates.waiting_regen_fb)
async def fb_regen(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message):
        return
    data = await state.get_data()
    aid = int(data.get("article_id") or 0)
    regen = data.get("regen_count", 0)
    await state.clear()
    fb = message.text or ""
    extra = None if _is_skip(fb) else fb
    if extra:
        await db.update_article(aid, admin_feedback=extra)
    await message.answer("🔄 Генерирую заново…")
    old_hint = await db.get_article_length_hint(aid)
    try:
        res = await content.generate_article(
            extra_rules=extra, length_hint=old_hint)
    except Exception as e:
        logger.exception("regen")
        await message.answer(f"❌ Ошибка регена: {e}")
        return
    if not res.get("ok"):
        await message.answer(f"🚫 Реген не прошёл цензуру: {res.get('reason','')[:400]}")
        return
    await db.update_article(res["article_id"], regen_count=regen + 1)
    await db.update_article(aid, status="rejected")
    await send_for_moderation(bot, res["article_id"])


@router.message(ModerationStates.waiting_reject_fb)
async def fb_reject(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message):
        return
    data = await state.get_data()
    aid = int(data.get("article_id") or 0)
    await state.clear()
    fb = message.text or ""
    await db.update_article(aid, status="rejected")
    extra = None
    if not _is_skip(fb):
        await db.update_article(aid, admin_feedback=fb)
        await db.append_setting("censor_extra", fb)
        extra = fb
    await message.answer("❌ Отклонено. 🔄 Генерирую заново с учётом замечаний…")
    old_hint = await db.get_article_length_hint(aid)
    try:
        res = await content.generate_article(
            extra_rules=extra, length_hint=old_hint)
    except Exception as e:
        logger.exception("reject-regen")
        await message.answer(f"❌ Ошибка регена: {e}")
        return
    if not res.get("ok"):
        await message.answer(f"🚫 Реген не прошёл цензуру: {res.get('reason','')[:400]}")
        return
    await send_for_moderation(bot, res["article_id"])
