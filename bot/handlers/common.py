"""Subscription, language and menu handlers: /start, /stop, /lang, /help, /menu."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.db import VerbaDB
from bot.i18n import DEFAULT_LANG, LANGS, t
from bot.keyboards import (
    GROUP_LANG_CB_PREFIX,
    LANG_CB_PREFIX,
    lang_keyboard,
    menu_keyboard,
)

log = logging.getLogger(__name__)
router = Router()

GROUP_TYPES = {"group", "supergroup"}


def user_lang(db: VerbaDB, user_id: int) -> str:
    user = db.get_user(user_id)
    return user.lang if user else DEFAULT_LANG


def effective_lang(db: VerbaDB, message: Message) -> str:
    """Group language in groups, the user's language in private chats."""
    if message.chat.type in GROUP_TYPES:
        return db.get_chat_lang(message.chat.id)
    if message.from_user:
        return user_lang(db, message.from_user.id)
    return DEFAULT_LANG


@router.message(Command("start"))
async def cmd_start(message: Message, db: VerbaDB) -> None:
    if message.from_user is None:
        return
    db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    db.set_subscribed(message.from_user.id, True)
    lang = user_lang(db, message.from_user.id)
    await message.answer(t("welcome", lang), reply_markup=menu_keyboard(lang))


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


@router.message(Command("help"))
@router.message(Command("menu"))
async def cmd_menu(message: Message, db: VerbaDB) -> None:
    lang = effective_lang(db, message)
    await message.answer(t("menu_title", lang), reply_markup=menu_keyboard(lang))


@router.message(Command("lang"))
async def cmd_lang(message: Message, db: VerbaDB) -> None:
    lang = effective_lang(db, message)
    scope = "group" if message.chat.type in GROUP_TYPES else "user"
    await message.answer(t("lang_choose", lang), reply_markup=lang_keyboard(scope))


@router.callback_query(F.data.startswith(GROUP_LANG_CB_PREFIX))
async def on_group_lang(query: CallbackQuery, db: VerbaDB) -> None:
    if query.data is None or not isinstance(query.message, Message):
        await query.answer()
        return
    lang = query.data.removeprefix(GROUP_LANG_CB_PREFIX)
    if lang not in LANGS:
        await query.answer()
        return
    db.set_chat_lang(query.message.chat.id, lang)
    await query.message.edit_text(t("lang_set_group", lang))
    await query.answer()


@router.callback_query(F.data.startswith(LANG_CB_PREFIX))
async def on_lang(query: CallbackQuery, db: VerbaDB) -> None:
    if query.from_user is None or query.data is None:
        await query.answer()
        return
    lang = query.data.removeprefix(LANG_CB_PREFIX)
    if lang not in LANGS:
        await query.answer()
        return
    db.add_user(query.from_user.id, query.from_user.username, query.from_user.first_name)
    db.set_lang(query.from_user.id, lang)
    if isinstance(query.message, Message):
        await query.message.edit_text(t("lang_set", lang))
    await query.answer()
