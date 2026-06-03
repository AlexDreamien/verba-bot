"""Game handlers: /play, /broadcast (admin), /stats, /me."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.broadcast import broadcast_daily, send_play
from bot.config import Config
from bot.daily import day_key
from bot.db import VerbaDB
from bot.handlers.common import user_lang
from bot.i18n import t
from bot.keyboards import play_link_keyboard
from bot.stats import compute_daily, compute_user, format_daily, format_user

log = logging.getLogger(__name__)
router = Router()


def _today(config: Config) -> str:
    return day_key(datetime.now(UTC), config.tz)


@router.message(Command("play"))
async def cmd_play(message: Message, db: VerbaDB, config: Config, bot_username: str) -> None:
    if message.from_user is None:
        return
    lang = user_lang(db, message.from_user.id)
    if not config.webapp_url:
        await message.answer(t("no_webapp", lang))
        return
    db.add_user(message.from_user.id, message.from_user.username)
    if message.chat.type == "private":
        await send_play(message.bot, message.chat.id, config, lang)
    else:
        # web_app buttons are private-chat only; point group users to the bot DM.
        await message.answer(
            t("play_in_private", lang),
            reply_markup=play_link_keyboard(bot_username, lang),
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
    if message.from_user is None:
        return
    lang = user_lang(db, message.from_user.id)
    day = _today(config)
    stats = compute_daily(db.daily_rows(day))
    await message.answer(format_daily(stats, day, lang))


@router.message(Command("me"))
async def cmd_me(message: Message, db: VerbaDB) -> None:
    if message.from_user is None:
        return
    lang = user_lang(db, message.from_user.id)
    stats = compute_user(db.user_history(message.from_user.id))
    await message.answer(format_user(stats, lang))
