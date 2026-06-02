"""Tests for the day-key formatting that must match the engine's dayKey."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bot.daily import day_key, parse_day


def test_month_zero_padded_day_not_padded():
    # 2026-05-01 09:00 UTC -> Kyiv summer (UTC+3) = 12:00 on the 1st.
    dt = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)
    assert day_key(dt, "Europe/Kyiv") == "1.05.2026"


def test_two_digit_day():
    dt = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
    assert day_key(dt, "Europe/Kyiv") == "20.03.2026"


def test_timezone_rollover_after_midnight_kyiv():
    # 22:30 UTC on May 1 is 01:30 on May 2 in Kyiv (UTC+3).
    dt = datetime(2026, 5, 1, 22, 30, tzinfo=UTC)
    assert day_key(dt, "Europe/Kyiv") == "2.05.2026"


def test_naive_datetime_treated_as_utc():
    naive = datetime(2026, 5, 1, 9, 0)
    assert day_key(naive, "Europe/Kyiv") == "1.05.2026"


def test_parse_day_roundtrip():
    assert parse_day("1.05.2026") == (2026, 5, 1)
    assert parse_day("20.03.2022") == (2022, 3, 20)


def test_parse_day_malformed():
    with pytest.raises(ValueError):
        parse_day("not-a-day")
