"""Game + menu handlers: /play, /broadcast, /stats, /me, menu buttons, mentions.

This router is included LAST, so its catch-all text handler (for mentions /
unknown text -> menu) never shadows the command handlers in other routers.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)

from bot.broadcast import broadcast_daily, send_play
from bot.config import Config
from bot.daily import day_key
from bot.db import VerbaDB
from bot.handlers.common import GROUP_TYPES, effective_lang, is_admin_here, user_lang
from bot.i18n import t
from bot.keyboards import MENU_CB_PREFIX, lang_keyboard, menu_keyboard, play_link_keyboard
from bot.stats import (
    compute_daily,
    compute_user,
    format_competition,
    format_daily,
    format_user,
)

log = logging.getLogger(__name__)
router = Router()


def _today(config: Config) -> str:
    return day_key(datetime.now(UTC), config.tz)


async def _send_stats(bot, chat, db: VerbaDB, config: Config, lang: str) -> None:
    if chat.type in GROUP_TYPES:
        # In a group, /stats is the competition leaderboard for the current season.
        season, _ = db.get_season(chat.id)
        standings = db.competition_standings(chat.id)
        await bot.send_message(chat.id, format_competition(standings, season, lang))
    else:
        day = _today(config)
        await bot.send_message(chat.id, format_daily(compute_daily(db.daily_rows(day)), day, lang))


async def _send_play(bot, chat, db: VerbaDB, config: Config, lang: str, bot_username: str) -> None:
    if not config.webapp_url:
        await bot.send_message(chat.id, t("no_webapp", lang))
    elif chat.type in GROUP_TYPES:
        await bot.send_message(
            chat.id,
            t("play_in_private", lang),
            reply_markup=play_link_keyboard(bot_username, lang, chat.id),
        )
    else:
        await send_play(bot, chat.id, config, lang)


@router.message(Command("play"))
async def cmd_play(message: Message, db: VerbaDB, config: Config, bot_username: str) -> None:
    if message.from_user:
        db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await _send_play(
        message.bot, message.chat, db, config, effective_lang(db, message), bot_username
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, db: VerbaDB, config: Config) -> None:
    if message.from_user is None:
        return
    lang = user_lang(db, message.from_user.id)
    if message.from_user.id not in config.admin_ids:
        await message.answer(t("broadcast_not_admin", lang))
        return
    if not config.webapp_url:
        await message.answer(t("no_webapp", lang))
        return
    if not db.subscriber_ids():
        await message.answer(t("broadcast_no_subs", lang))
        return
    delivered, total = await broadcast_daily(message.bot, db, config)
    await message.answer(t("broadcast_done", lang, ok=delivered, total=total))


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: VerbaDB, config: Config) -> None:
    await _send_stats(message.bot, message.chat, db, config, effective_lang(db, message))


@router.message(Command("me"))
async def cmd_me(message: Message, db: VerbaDB) -> None:
    if message.from_user is None:
        return
    lang = effective_lang(db, message)
    stats = compute_user(db.user_history(message.from_user.id))
    await message.answer(format_user(stats, lang))


@router.callback_query(F.data.startswith(MENU_CB_PREFIX))
async def on_menu(query: CallbackQuery, db: VerbaDB, config: Config, bot_username: str) -> None:
    if query.data is None or query.from_user is None or not isinstance(query.message, Message):
        await query.answer()
        return
    action = query.data.removeprefix(MENU_CB_PREFIX)
    chat = query.message.chat
    is_group = chat.type in GROUP_TYPES
    # Use the requesting user (query.from_user), NOT the message author (the bot).
    lang = db.get_chat_lang(chat.id) if is_group else user_lang(db, query.from_user.id)
    db.add_user(query.from_user.id, query.from_user.username, query.from_user.first_name)
    bot = query.bot

    if action == "play":
        await _send_play(bot, chat, db, config, lang, bot_username)
    elif action == "stats":
        await _send_stats(bot, chat, db, config, lang)
    elif action == "me":
        stats = compute_user(db.user_history(query.from_user.id))
        await bot.send_message(chat.id, format_user(stats, lang))
    elif action == "lang":
        scope = "group" if is_group else "user"
        await bot.send_message(chat.id, t("lang_choose", lang), reply_markup=lang_keyboard(scope))
    elif action == "help":
        admin = await is_admin_here(bot, chat, query.from_user.id, config)
        await bot.send_message(
            chat.id, t("menu_title", lang), reply_markup=menu_keyboard(lang, admin)
        )
    await query.answer()


@router.inline_query()
async def on_inline(query: InlineQuery, db: VerbaDB, bot_username: str) -> None:
    """Let players share their result grid into any chat (requires inline mode).

    The Mini App's share button puts the emoji grid into the inline query; we echo
    it back as the message, with a promo line linking to the bot.
    """
    lang = user_lang(db, query.from_user.id) if query.from_user else "uk"
    grid = (query.query or "").strip()
    promo = t("share_promo", lang, bot=bot_username)
    message_text = f"{grid}\n\n{promo}" if grid else promo
    result = InlineQueryResultArticle(
        id="verba-share",
        title=t("share_title", lang),
        description=grid[:60] or "Verba",
        input_message_content=InputTextMessageContent(message_text=message_text),
    )
    await query.answer([result], cache_time=1, is_personal=True)


@router.message(F.text)
async def on_text(message: Message, db: VerbaDB, config: Config, bot_username: str) -> None:
    """Fallback: show the menu on plain text (private) or on a mention (groups)."""
    text = message.text or ""
    if text.startswith("/"):
        return  # commands are handled by their own handlers
    # In groups, only react when the bot is actually mentioned.
    if message.chat.type in GROUP_TYPES and (
        not bot_username or f"@{bot_username}".lower() not in text.lower()
    ):
        return
    lang = effective_lang(db, message)
    is_admin = message.from_user is not None and await is_admin_here(
        message.bot, message.chat, message.from_user.id, config
    )
    await message.answer(t("menu_title", lang), reply_markup=menu_keyboard(lang, is_admin))
