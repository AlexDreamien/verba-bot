"""Inline keyboards (thin aiogram layer)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.i18n import t

__all__ = ["LANG_CB_PREFIX", "lang_keyboard", "play_keyboard"]

LANG_CB_PREFIX = "lang:"


def play_keyboard(webapp_url: str, lang: str) -> InlineKeyboardMarkup:
    """A single button that opens the Mini App inside Telegram.

    Telegram requires an HTTPS URL for ``web_app`` buttons.
    """
    button = InlineKeyboardButton(
        text=t("play_button", lang),
        web_app=WebAppInfo(url=webapp_url),
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇦 Українська", callback_data=f"{LANG_CB_PREFIX}uk"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"{LANG_CB_PREFIX}ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data=f"{LANG_CB_PREFIX}en"),
            ]
        ]
    )
