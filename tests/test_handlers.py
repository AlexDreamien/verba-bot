"""Tests for handler-layer helpers (no aiogram runtime needed)."""

from __future__ import annotations

from bot.handlers.common import (
    STATS_COOLDOWN_SEC,
    group_stats_on_cooldown,
    mark_group_stats,
)


def test_group_stats_cooldown():
    chat, user = -777, 42
    assert group_stats_on_cooldown(chat, user) is False  # never asked
    mark_group_stats(chat, user)
    assert group_stats_on_cooldown(chat, user) is True  # within the window
    # A different user in the same chat is independent.
    assert group_stats_on_cooldown(chat, 99) is False
    assert STATS_COOLDOWN_SEC == 3600
