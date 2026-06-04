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
from bot.handlers.common import (
    GROUP_TYPES,
    dm,
    effective_lang,
    group_stats_on_cooldown,
    is_admin_here,
    mark_group_stats,
    respond,
    user_lang,
)
from bot.i18n import t
from bot.keyboards import (
    MENU_CB_PREFIX,
    lang_keyboard,
    menu_keyboard,
    play_keyboard,
    play_link_keyboard,
)
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


async def _post_leaderboard(bot, chat, db: VerbaDB, requester_id: int, config: Config) -> bool:
    """Post the group's season leaderboard, honoring the non-admin 1/hour cooldown.

    Returns False (without posting) when a non-admin is on cooldown.
    """
    admin = await is_admin_here(bot, chat, requester_id, config)
    if not admin and group_stats_on_cooldown(chat.id, requester_id):
        return False
    season, _ = db.get_season(chat.id)
    standings = db.competition_standings(chat.id)
    await bot.send_message(
        chat.id, format_competition(standings, season, db.get_chat_lang(chat.id))
    )
    if not admin:
        mark_group_stats(chat.id, requester_id)
    return True


@router.message(Command("play"))
async def cmd_play(message: Message, db: VerbaDB, config: Config, bot_username: str) -> None:
    if message.from_user is None:
        return
    db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    lang = user_lang(db, message.from_user.id)
    if not config.webapp_url:
        await respond(message, db, bot_username, t("no_webapp", lang))
        return
    if message.chat.type in GROUP_TYPES:
        # web_app buttons only work in private chats -> send the game to the DM.
        try:
            await send_play(message.bot, message.from_user.id, config, lang)
        except Exception:  # noqa: BLE001 — user hasn't opened the bot: offer a deep link
            await message.reply(
                t("play_in_private", lang),
                reply_markup=play_link_keyboard(bot_username, lang, message.chat.id),
            )
    else:
        await send_play(message.bot, message.chat.id, config, lang)


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
    if message.from_user is None:
        return
    if message.chat.type in GROUP_TYPES:
        posted = await _post_leaderboard(
            message.bot, message.chat, db, message.from_user.id, config
        )
        if not posted:  # on cooldown -> tell them quietly in DM, no group spam
            await dm(
                message.bot,
                message.from_user.id,
                t("stats_cooldown", user_lang(db, message.from_user.id)),
            )
        return
    day = _today(config)
    await message.answer(
        format_daily(compute_daily(db.daily_rows(day)), day, effective_lang(db, message))
    )


@router.message(Command("me"))
async def cmd_me(message: Message, db: VerbaDB, bot_username: str) -> None:
    if message.from_user is None:
        return
    lang = user_lang(db, message.from_user.id)
    stats = compute_user(db.user_history(message.from_user.id))
    await respond(message, db, bot_username, format_user(stats, lang))


@router.callback_query(F.data.startswith(MENU_CB_PREFIX))
async def on_menu(query: CallbackQuery, db: VerbaDB, config: Config, bot_username: str) -> None:
    if query.data is None or query.from_user is None or not isinstance(query.message, Message):
        await query.answer()
        return
    action = query.data.removeprefix(MENU_CB_PREFIX)
    chat = query.message.chat
    is_group = chat.type in GROUP_TYPES
    uid = query.from_user.id
    ulang = user_lang(db, uid)  # the requester's language (not the message author/bot)
    db.add_user(uid, query.from_user.username, query.from_user.first_name)
    bot = query.bot

    # The leaderboard stays in the group (rate-limited for non-admins); the daily
    # summary in a private chat. Everything else is delivered to the user's DM.
    if action == "stats":
        if is_group:
            posted = await _post_leaderboard(bot, chat, db, uid, config)
            await query.answer("" if posted else t("stats_cooldown", ulang), show_alert=not posted)
        else:
            day = _today(config)
            await bot.send_message(
                chat.id, format_daily(compute_daily(db.daily_rows(day)), day, ulang)
            )
            await query.answer()
        return

    if action == "play":
        text, markup = (
            (t("no_webapp", ulang), None)
            if not config.webapp_url
            else (t("play_prompt", ulang), play_keyboard(config.webapp_url, ulang))
        )
    elif action == "me":
        text, markup = format_user(compute_user(db.user_history(uid)), ulang), None
    elif action == "lang":
        text, markup = t("lang_choose", ulang), lang_keyboard("user")
    elif action == "help":
        admin = await is_admin_here(bot, chat, uid, config)
        text, markup = t("menu_title", ulang), menu_keyboard(ulang, admin)
    else:
        await query.answer()
        return

    if is_group:
        ok = await dm(bot, uid, text, markup)
        await query.answer(
            t("sent_to_dm", ulang) if ok else t("dm_first", ulang, bot=bot_username),
            show_alert=not ok,
        )
    else:
        await bot.send_message(chat.id, text, reply_markup=markup)
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
    if message.from_user is None:
        return
    is_admin = await is_admin_here(message.bot, message.chat, message.from_user.id, config)
    lang = user_lang(db, message.from_user.id)
    await respond(message, db, bot_username, t("menu_title", lang), menu_keyboard(lang, is_admin))
