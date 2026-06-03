"""Register every handler router on a Dispatcher."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Dispatcher
from aiogram.types import Message

from bot.config import Config
from bot.db import VerbaDB
from bot.handlers import common, game

__all__ = ["setup"]

GROUP_TYPES = {"group", "supergroup"}


class MembershipMiddleware(BaseMiddleware):
    """Record which users the bot sees in which group chats.

    Runs on every incoming message; in group chats it upserts the sender into
    ``memberships`` (and the chat title). With privacy mode disabled this tracks
    everyone who talks; with it enabled, everyone who interacts with the bot.
    """

    def __init__(self, db: VerbaDB) -> None:
        self._db = db

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        chat = event.chat
        user = event.from_user
        if chat and chat.type in GROUP_TYPES and user and not user.is_bot:
            try:
                self._db.track_membership(chat.id, user.id, user.username, user.first_name)
                self._db.upsert_chat(chat.id, chat.title)
            except Exception:  # noqa: BLE001 — tracking must never break handling
                pass
        return await handler(event, data)


def setup(dp: Dispatcher, db: VerbaDB, config: Config) -> None:
    """Wire shared dependencies and include the routers."""
    dp["db"] = db
    dp["config"] = config
    dp.message.outer_middleware(MembershipMiddleware(db))
    dp.include_router(common.router)
    dp.include_router(game.router)  # included last (has the catch-all text handler)
