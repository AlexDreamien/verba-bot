"""Tests for config parsing helpers."""

from __future__ import annotations

import pytest

from bot.config import load_config, parse_admin_ids


def test_parse_admin_ids_empty():
    assert parse_admin_ids(None) == frozenset()
    assert parse_admin_ids("") == frozenset()


def test_parse_admin_ids_list():
    assert parse_admin_ids("1, 2 ,3") == frozenset({1, 2, 3})


def test_parse_admin_ids_ignores_blanks():
    assert parse_admin_ids("10,,20,") == frozenset({10, 20})


def test_load_config_requires_token():
    with pytest.raises(SystemExit):
        load_config({"ADMIN_IDS": "1"})


def test_load_config_defaults():
    cfg = load_config({"BOT_TOKEN": "x", "ADMIN_IDS": "1,2", "BROADCAST_CRON": ""})
    assert cfg.bot_token == "x"
    assert cfg.admin_ids == frozenset({1, 2})
    assert cfg.broadcast_cron is None  # empty string disables it
    assert cfg.tz == "Europe/Kyiv"
    assert cfg.summary_to_subscribers is False
