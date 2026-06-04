"""Inline keyboards (thin aiogram layer)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.i18n import t

__all__ = [
    "GROUP_LANG_CB_PREFIX",
    "LANG_CB_PREFIX",
    "MENU_CB_PREFIX",
    "lang_keyboard",
    "menu_keyboard",
    "play_keyboard",
    "play_link_keyboard",
]

LANG_CB_PREFIX = "lang:"
GROUP_LANG_CB_PREFIX = "glang:"
MENU_CB_PREFIX = "menu:"


def menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Quick-action menu shown on /menu, /help, or when the bot is mentioned."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("play_button", lang), callback_data=f"{MENU_CB_PREFIX}play"
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_stats", lang), callback_data=f"{MENU_CB_PREFIX}stats"
                ),
                InlineKeyboardButton(text=t("btn_me", lang), callback_data=f"{MENU_CB_PREFIX}me"),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_lang", lang), callback_data=f"{MENU_CB_PREFIX}lang"
                ),
                InlineKeyboardButton(
                    text=t("btn_help", lang), callback_data=f"{MENU_CB_PREFIX}help"
                ),
            ],
        ]
    )


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


def play_link_keyboard(
    bot_username: str, lang: str, chat_id: int | None = None
) -> InlineKeyboardMarkup:
    """A URL button that opens the bot's private chat (for group chats).

    ``web_app`` buttons can't be used in groups, so we send users to the private
    chat with the bot, where the Mini App (and result reporting) works fully.
    When ``chat_id`` is given, the link carries a ``reg_<chat_id>`` start payload
    so ``/start`` auto-registers the user into that group's competition.
    """
    url = f"https://t.me/{bot_username}"
    if chat_id is not None:
        url += f"?start=reg_{chat_id}"
    button = InlineKeyboardButton(text=t("play_button", lang), url=url)
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def lang_keyboard(scope: str = "user") -> InlineKeyboardMarkup:
    """Language picker. ``scope="group"`` sets the group's language instead of
    the user's (different callback prefix)."""
    prefix = GROUP_LANG_CB_PREFIX if scope == "group" else LANG_CB_PREFIX
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇦 Українська", callback_data=f"{prefix}uk"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"{prefix}ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data=f"{prefix}en"),
            ]
        ]
    )
