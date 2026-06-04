"""Tests for inline keyboard construction (manual / admin-manual buttons)."""

from __future__ import annotations

from bot.keyboards import menu_keyboard, play_link_keyboard


def _buttons(markup):
    return [b for row in markup.inline_keyboard for b in row]


def test_menu_has_player_manual_for_everyone():
    btns = _buttons(menu_keyboard("en"))
    urls = [b.url for b in btns if b.url]
    assert any("MANUAL-USERS" in u for u in urls)
    assert not any("MANUAL-ADMINS" in u for u in urls)  # no admin link by default


def test_menu_adds_admin_manual_for_admins():
    btns = _buttons(menu_keyboard("en", is_admin=True))
    urls = [b.url for b in btns if b.url]
    assert any("MANUAL-USERS" in u for u in urls)
    assert any("MANUAL-ADMINS" in u for u in urls)


def test_menu_manual_localized_uk_shares_ru():
    urls = [b.url for b in _buttons(menu_keyboard("uk")) if b.url]
    assert any(u.endswith("MANUAL-USERS.md") for u in urls)  # uk -> RU manual
    urls_en = [b.url for b in _buttons(menu_keyboard("en")) if b.url]
    assert any(u.endswith("MANUAL-USERS.en.md") for u in urls_en)


def test_play_link_deep_link_register():
    kb = play_link_keyboard("VerbaGame_bot", "en", chat_id=-1001234567890)
    url = _buttons(kb)[0].url
    assert url == "https://t.me/VerbaGame_bot?start=reg_-1001234567890"
