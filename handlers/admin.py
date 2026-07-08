import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

import config
from db import database as db
from services import content, publisher

logger = logging.getLogger(__name__)
router = Router(name="admin")


def _is_admin_id(uid: int) -> bool:
    return bool(config.ADMIN_CHAT_ID) and uid == config.ADMIN_CHAT_ID


def _is_admin(message: Message) -> bool:
    return _is_admin_id(message.from_user.id)


def _kb(article_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"pub:{article_id}"),
        InlineKeyboardButton(text="🔄 Заново", callback_data=f"regen:{article_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej:{article_id}"),
    ]])


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

    from pathlib import Path
    has_img = image_path and Path(image_path).exists()
    full = header + body
    if has_img and len(full) <= CAPTION_LIMIT:
        await bot.send_photo(config.ADMIN_CHAT_ID, FSInputFile(image_path),
                             caption=full, reply_markup=kb)
    else:
        if has_img:
            await bot.send_photo(config.ADMIN_CHAT_ID, FSInputFile(image_path))
        # текст: если длинный — режем, кнопки на последнем куске
        parts = publisher._split(body, 4000)
        for i, part in enumerate(parts):
            prefix = header if i == 0 else ""
            last = i == len(parts) - 1
            await bot.send_message(config.ADMIN_CHAT_ID, prefix + part,
                                   reply_markup=kb if last else None)


# ---------- команды ----------
@router.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(
        f"chat_id этого чата: <code>{message.chat.id}</code>\n"
        f"тип чата: {message.chat.type}\n"
        f"твой user_id: <code>{message.from_user.id}</code>"
    )


@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.chat.type != "private":
        return
    if not _is_admin(message):
        await message.answer(
            "Это служебный бот автоведения канала SMOKI.\n"
            f"Твой user_id: <code>{message.from_user.id}</code>\n"
            "Если ты администратор — впиши этот id в ADMIN_CHAT_ID (.env)."
        )
        return
    await message.answer(
        "👋 SMOKI content bot готов.\n\n"
        "Команды:\n"
        "/generate — сгенерировать черновик поста\n"
        "/id — показать id чата"
    )


@router.message(Command("generate"))
async def cmd_generate(message: Message, bot: Bot):
    if not _is_admin(message):
        return
    await message.answer("⏳ Генерирую черновик, подожди ~30-60 сек…")
    try:
        res = await content.generate_article()
    except Exception as e:
        logger.exception("generate")
        await message.answer(f"❌ Ошибка генерации: {e}")
        return
    if not res.get("ok"):
        await message.answer(f"🚫 Не прошло цензуру:\n{res.get('reason','')[:500]}")
        return
    await send_for_moderation(bot, res["article_id"])


# ---------- модерация (callbacks) ----------
@router.callback_query(F.data.startswith("pub:"))
async def cb_publish(cq: CallbackQuery, bot: Bot):
    if not _is_admin_id(cq.from_user.id):
        await cq.answer("Не для тебя", show_alert=True)
        return
    aid = int(cq.data.split(":")[1])
    await cq.answer("Публикую…")
    res = await publisher.publish_article(bot, aid)
    if res["ok"]:
        await cq.message.edit_reply_markup(reply_markup=None)
        await bot.send_message(config.ADMIN_CHAT_ID,
                               f"✅ Статья #{aid} опубликована (msg {res['message_id']}).")
    else:
        await bot.send_message(config.ADMIN_CHAT_ID,
                               f"❌ Ошибка публикации #{aid}: {res['error']}")


@router.callback_query(F.data.startswith("regen:"))
async def cb_regen(cq: CallbackQuery, bot: Bot):
    if not _is_admin_id(cq.from_user.id):
        await cq.answer("Не для тебя", show_alert=True)
        return
    aid = int(cq.data.split(":")[1])
    old = await db.get_article(aid)
    regen = (old.get("regen_count") or 0) if old else 0
    if regen >= config.MAX_REGEN:
        await cq.answer(f"Лимит перегенераций ({config.MAX_REGEN}) исчерпан", show_alert=True)
        return
    await cq.answer("Генерирую заново…")
    try:
        res = await content.generate_article()  # новая тема
    except Exception as e:
        await bot.send_message(config.ADMIN_CHAT_ID, f"❌ Ошибка регена: {e}")
        return
    if not res.get("ok"):
        await bot.send_message(config.ADMIN_CHAT_ID,
                               f"🚫 Реген не прошёл цензуру: {res.get('reason','')[:400]}")
        return
    # перенос счётчика
    await db.update_article(res["article_id"], regen_count=regen + 1)
    await db.update_article(aid, status="rejected")
    await cq.message.edit_reply_markup(reply_markup=None)
    await send_for_moderation(bot, res["article_id"])


@router.callback_query(F.data.startswith("rej:"))
async def cb_reject(cq: CallbackQuery):
    if not _is_admin_id(cq.from_user.id):
        await cq.answer("Не для тебя", show_alert=True)
        return
    aid = int(cq.data.split(":")[1])
    await db.update_article(aid, status="rejected")
    await cq.answer("Отклонено")
    await cq.message.edit_reply_markup(reply_markup=None)
