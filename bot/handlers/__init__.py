"""Register every handler router on a Dispatcher."""

from __future__ import annotations

from aiogram import Dispatcher

from bot.config import Config
from bot.db import VerbaDB
from bot.handlers import common, game

__all__ = ["setup"]


def setup(dp: Dispatcher, db: VerbaDB, config: Config) -> None:
    """Wire shared dependencies and include the routers."""
    dp["db"] = db
    dp["config"] = config
    dp.include_router(common.router)
    dp.include_router(game.router)
