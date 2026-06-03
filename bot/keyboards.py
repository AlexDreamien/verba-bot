"""Inline keyboards (thin aiogram layer)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.i18n import t

__all__ = ["LANG_CB_PREFIX", "lang_keyboard", "play_keyboard", "play_link_keyboard"]

LANG_CB_PREFIX = "lang:"


def play_keyboard(webapp_url: str, lang: str) -> InlineKeyboardMarkup:
    """A single button that opens the Mini App inside Telegram.

    Telegram requires an HTTPS URL for ``web_app`` buttons, and such buttons are
    only allowed in **private** chats — use :func:`play_link_keyboard` elsewhere.
    """
    button = InlineKeyboardButton(
        text=t("play_button", lang),
        web_app=WebAppInfo(url=webapp_url),
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def play_link_keyboard(bot_username: str, lang: str) -> InlineKeyboardMarkup:
    """A URL button that opens the bot's private chat (for group chats).

    ``web_app`` buttons can't be used in groups, so we send users to the private
    chat with the bot, where the Mini App (and result reporting) works fully.
    """
    button = InlineKeyboardButton(
        text=t("play_button", lang),
        url=f"https://t.me/{bot_username}",
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
