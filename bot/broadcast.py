"""Sending the daily game link to users.

Shared by the ``/broadcast`` admin command and the scheduled daily job, so the
delivery logic lives in one place. Kept thin (it talks to the Bot API) but free
of handler/router wiring.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from bot.config import Config
from bot.db import VerbaDB
from bot.i18n import DEFAULT_LANG, t
from bot.keyboards import play_keyboard

__all__ = ["send_play", "broadcast_daily"]

log = logging.getLogger(__name__)


async def send_play(bot: Bot, chat_id: int, config: Config, lang: str) -> None:
    """Send one user the play prompt with the Mini App button."""
    await bot.send_message(
        chat_id,
        t("play_prompt", lang),
        reply_markup=play_keyboard(config.webapp_url, lang),
    )


async def broadcast_daily(bot: Bot, db: VerbaDB, config: Config) -> tuple[int, int]:
    """Send the game to every subscriber. Returns ``(delivered, total)``.

    Users who have blocked the bot are auto-unsubscribed so they drop out of
    future broadcasts.
    """
    subscribers = db.list_subscribers()
    delivered = 0
    for user in subscribers:
        lang = user.lang or DEFAULT_LANG
        try:
            await send_play(bot, user.user_id, config, lang)
            delivered += 1
        except TelegramForbiddenError:
            log.info("User %d blocked the bot; unsubscribing", user.user_id)
            db.set_subscribed(user.user_id, False)
        except Exception:
            log.exception("Failed to send daily game to %d", user.user_id)
        await asyncio.sleep(0.05)  # stay well under Telegram's rate limits
    return delivered, len(subscribers)
