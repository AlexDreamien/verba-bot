"""Subscription and language handlers: /start, /stop, /lang, /help."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.db import VerbaDB
from bot.i18n import DEFAULT_LANG, LANGS, t
from bot.keyboards import LANG_CB_PREFIX, lang_keyboard

log = logging.getLogger(__name__)
router = Router()


def user_lang(db: VerbaDB, user_id: int) -> str:
    user = db.get_user(user_id)
    return user.lang if user else DEFAULT_LANG


@router.message(Command("start"))
async def cmd_start(message: Message, db: VerbaDB) -> None:
    if message.from_user is None:
        return
    db.add_user(message.from_user.id, message.from_user.username)
    db.set_subscribed(message.from_user.id, True)
    await message.answer(t("welcome", user_lang(db, message.from_user.id)))


@router.message(Command("stop"))
async def cmd_stop(message: Message, db: VerbaDB) -> None:
    if message.from_user is None:
        return
    lang = user_lang(db, message.from_user.id)
    user = db.get_user(message.from_user.id)
    if user is None or not user.subscribed:
        await message.answer(t("not_subscribed", lang))
        return
    db.set_subscribed(message.from_user.id, False)
    await message.answer(t("unsubscribed", lang))


@router.message(Command("lang"))
async def cmd_lang(message: Message, db: VerbaDB) -> None:
    if message.from_user is None:
        return
    await message.answer(
        t("lang_choose", user_lang(db, message.from_user.id)), reply_markup=lang_keyboard()
    )


@router.callback_query(F.data.startswith(LANG_CB_PREFIX))
async def on_lang(query: CallbackQuery, db: VerbaDB) -> None:
    if query.from_user is None or query.data is None:
        await query.answer()
        return
    lang = query.data.removeprefix(LANG_CB_PREFIX)
    if lang not in LANGS:
        await query.answer()
        return
    db.add_user(query.from_user.id, query.from_user.username)
    db.set_lang(query.from_user.id, lang)
    if isinstance(query.message, Message):
        await query.message.edit_text(t("lang_set", lang))
    await query.answer()
