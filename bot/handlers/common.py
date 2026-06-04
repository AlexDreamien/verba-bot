"""Subscription, language and menu handlers: /start, /stop, /lang, /help, /menu."""

from __future__ import annotations

import logging
import time

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.db import VerbaDB
from bot.i18n import DEFAULT_LANG, LANGS, t
from bot.keyboards import (
    GROUP_LANG_CB_PREFIX,
    LANG_CB_PREFIX,
    lang_keyboard,
    menu_keyboard,
    play_keyboard,
)
from bot.stats import display_name, format_competition, format_seasons

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


# --- private-delivery helpers (keep group chats spam-free) -----------------


async def dm(bot, user_id: int, text: str, reply_markup=None) -> bool:
    """Send to a user's private chat. Returns False if the bot can't reach them."""
    try:
        await bot.send_message(user_id, text, reply_markup=reply_markup)
        return True
    except Exception:  # noqa: BLE001 — user hasn't opened the bot, blocked it, etc.
        return False


# Non-admins may pull the group leaderboard at most once per hour (per chat).
STATS_COOLDOWN_SEC = 3600
_stats_seen: dict[tuple[int, int], float] = {}


def group_stats_on_cooldown(chat_id: int, user_id: int) -> bool:
    last = _stats_seen.get((chat_id, user_id))
    return last is not None and (time.monotonic() - last) < STATS_COOLDOWN_SEC


def mark_group_stats(chat_id: int, user_id: int) -> None:
    _stats_seen[(chat_id, user_id)] = time.monotonic()


async def respond(
    message: Message, db: VerbaDB, bot_username: str, text: str, reply_markup=None
) -> None:
    """Reply in place in a private chat; in a group, send to the user's DM instead
    (so the group stays free of per-user spam). Falls back to a short group hint
    if the bot can't message the user."""
    if message.chat.type in GROUP_TYPES and message.from_user is not None:
        if not await dm(message.bot, message.from_user.id, text, reply_markup):
            await message.reply(t("dm_first", effective_lang(db, message), bot=bot_username))
    else:
        await message.answer(text, reply_markup=reply_markup)


@router.message(F.migrate_to_chat_id)
async def on_migrate(message: Message, db: VerbaDB) -> None:
    """Remap stored data when a group is upgraded to a supergroup (id changes)."""
    new_id = message.migrate_to_chat_id
    if new_id is not None:
        db.migrate_chat(message.chat.id, new_id)
        log.info("Chat migrated: %d -> %d", message.chat.id, new_id)


@router.message(Command("start"))
async def cmd_start(message: Message, db: VerbaDB, config: Config, command: CommandObject) -> None:
    if message.from_user is None:
        return
    db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    db.set_subscribed(message.from_user.id, True)
    lang = user_lang(db, message.from_user.id)
    # Deep link from a group's Play button: t.me/<bot>?start=reg_<chat_id>
    arg = (command.args or "").strip()
    if arg.startswith("reg_"):
        try:
            chat_id = int(arg.removeprefix("reg_"))
        except ValueError:
            chat_id = None
        if chat_id is not None:
            db.register(chat_id, message.from_user.id)
            markup = play_keyboard(config.webapp_url, lang) if config.webapp_url else None
            await message.answer(t("register_done_dm", lang), reply_markup=markup)
            return
    is_admin = message.from_user.id in config.admin_ids
    await message.answer(t("welcome", lang), reply_markup=menu_keyboard(lang, is_admin))


@router.message(Command("stop"))
async def cmd_stop(message: Message, db: VerbaDB, bot_username: str) -> None:
    if message.from_user is None:
        return
    lang = user_lang(db, message.from_user.id)
    user = db.get_user(message.from_user.id)
    if user is None or not user.subscribed:
        await respond(message, db, bot_username, t("not_subscribed", lang))
        return
    db.set_subscribed(message.from_user.id, False)
    await respond(message, db, bot_username, t("unsubscribed", lang))


@router.message(Command("register"))
async def cmd_register(message: Message, db: VerbaDB) -> None:
    if message.from_user is None:
        return
    if message.chat.type not in GROUP_TYPES:
        await message.answer(t("register_in_group", user_lang(db, message.from_user.id)))
        return
    db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    db.track_membership(
        message.chat.id,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    db.upsert_chat(message.chat.id, message.chat.title)
    newly = db.register(message.chat.id, message.from_user.id)
    lang = db.get_chat_lang(message.chat.id)
    name = display_name(
        message.from_user.first_name, message.from_user.username, message.from_user.id
    )
    await message.answer(t("register_done" if newly else "register_already", lang, name=name))


@router.message(Command("unregister"))
async def cmd_unregister(message: Message, db: VerbaDB) -> None:
    if message.from_user is None:
        return
    if message.chat.type not in GROUP_TYPES:
        await message.answer(t("group_only", user_lang(db, message.from_user.id)))
        return
    removed = db.unregister(message.chat.id, message.from_user.id)
    lang = db.get_chat_lang(message.chat.id)
    name = display_name(
        message.from_user.first_name, message.from_user.username, message.from_user.id
    )
    await message.answer(t("unregister_done" if removed else "unregister_not", lang, name=name))


async def is_admin_here(bot, chat, user_id: int, config: Config) -> bool:
    """True if ``user_id`` is a bot operator, or a Telegram admin/creator of the
    current group. In a private chat only the configured operators count."""
    if user_id in config.admin_ids:
        return True
    if chat.type in GROUP_TYPES:
        try:
            member = await bot.get_chat_member(chat.id, user_id)
        except Exception:  # noqa: BLE001 — treat any lookup failure as "not an admin"
            return False
        return getattr(member, "status", "") in ("administrator", "creator")
    return False


async def _is_group_admin(message: Message, config: Config) -> bool:
    """True if the sender may manage the group (admin/creator or bot operator)."""
    if message.from_user is None:
        return False
    return await is_admin_here(message.bot, message.chat, message.from_user.id, config)


@router.message(Command("startseason"))
async def cmd_startseason(message: Message, db: VerbaDB, config: Config) -> None:
    if message.from_user is None:
        return
    lang = effective_lang(db, message)
    if message.chat.type not in GROUP_TYPES:
        await message.answer(t("group_only", lang))
        return
    if not await _is_group_admin(message, config):
        await message.answer(t("season_not_admin", lang))
        return
    new_season = db.start_season(message.chat.id)
    if new_season is None:
        current, _ = db.get_season(message.chat.id)
        await message.answer(t("season_already", lang, n=current))
    else:
        await message.answer(t("season_started", lang, n=new_season))


@router.message(Command("finishseason"))
async def cmd_finishseason(message: Message, db: VerbaDB, config: Config) -> None:
    if message.from_user is None:
        return
    lang = effective_lang(db, message)
    if message.chat.type not in GROUP_TYPES:
        await message.answer(t("group_only", lang))
        return
    if not await _is_group_admin(message, config):
        await message.answer(t("season_not_admin", lang))
        return
    finished = db.finish_season(message.chat.id)
    if finished is None:
        await message.answer(t("season_none", lang))
        return
    standings = db.competition_standings(message.chat.id)
    if standings and standings[0].score > 0:
        top = standings[0]
        db.record_champion(message.chat.id, finished, top.user_id, top.score)
    board = format_competition(standings, finished, lang)
    await message.answer(t("season_finished", lang, n=finished) + "\n\n" + board)


@router.message(Command("seasons"))
async def cmd_seasons(message: Message, db: VerbaDB) -> None:
    if message.from_user is None:
        return
    if message.chat.type not in GROUP_TYPES:
        await message.answer(t("group_only", user_lang(db, message.from_user.id)))
        return
    lang = db.get_chat_lang(message.chat.id)
    await message.answer(format_seasons(db.season_history(message.chat.id), lang))


@router.message(Command("help"))
@router.message(Command("menu"))
async def cmd_menu(message: Message, db: VerbaDB, config: Config, bot_username: str) -> None:
    if message.from_user is None:
        return
    lang = user_lang(db, message.from_user.id)
    is_admin = await is_admin_here(message.bot, message.chat, message.from_user.id, config)
    await respond(message, db, bot_username, t("menu_title", lang), menu_keyboard(lang, is_admin))


@router.message(Command("lang"))
async def cmd_lang(message: Message, db: VerbaDB, config: Config, bot_username: str) -> None:
    if message.from_user is None:
        return
    # Group language is a group setting -> admins change it in-group; everyone
    # else gets a personal-language picker in their DM.
    if message.chat.type in GROUP_TYPES and await _is_group_admin(message, config):
        glang = db.get_chat_lang(message.chat.id)
        await message.answer(t("lang_choose", glang), reply_markup=lang_keyboard("group"))
        return
    ulang = user_lang(db, message.from_user.id)
    await respond(message, db, bot_username, t("lang_choose", ulang), lang_keyboard("user"))


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
