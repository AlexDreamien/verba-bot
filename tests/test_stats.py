"""Tests for the pure aggregation/formatting layer."""

from __future__ import annotations

from bot.db import Member, Result
from bot.stats import (
    compute_daily,
    compute_user,
    display_name,
    format_daily,
    format_duration,
    format_group_daily,
    format_user,
)


def r(user_id, day, status, attempts=None, elapsed_ms=None, lang=""):
    return Result(user_id, day, status, attempts, elapsed_ms, lang)


def test_display_name_priority():
    assert display_name("Alice", "al", 1) == "Alice"
    assert display_name(None, "al", 1) == "@al"
    assert display_name(None, None, 7) == "#7"


def test_format_group_daily():
    members = [Member(1, "alice", "Alice"), Member(2, None, "Bob"), Member(3, None, None)]
    rows = [
        r(1, "1.05.2026", "won", attempts=3, lang="ru"),
        r(2, "1.05.2026", "lost", attempts=6, lang="uk"),
    ]
    text = format_group_daily(members, rows, "1.05.2026", "en")
    assert "✅ Alice — 3/6" in text
    assert "❌ Bob" in text
    assert "💤 #3" in text  # no name, didn't play
    assert "of 3" in text


def test_format_group_daily_empty():
    assert "No members" in format_group_daily([], [], "1.05.2026", "en")


def test_compute_daily_counts_and_averages():
    rows = [
        r(1, "1.05.2026", "won", attempts=2, elapsed_ms=20000),
        r(2, "1.05.2026", "won", attempts=4, elapsed_ms=40000),
        r(3, "1.05.2026", "lost", attempts=6),
        r(4, "1.05.2026", "unfinished"),
        r(5, "1.05.2026", "not_played"),
    ]
    s = compute_daily(rows)
    assert s.total == 5
    assert (s.won, s.lost, s.unfinished, s.not_played) == (2, 1, 1, 1)
    assert s.avg_attempts == 3.0
    assert s.avg_elapsed_ms == 30000
    assert s.attempts_distribution == {2: 1, 4: 1}


def test_compute_daily_no_winners_has_no_averages():
    rows = [r(1, "1.05.2026", "lost", attempts=6), r(2, "1.05.2026", "not_played")]
    s = compute_daily(rows)
    assert s.won == 0
    assert s.avg_attempts is None
    assert s.avg_elapsed_ms is None


def test_format_daily_empty():
    s = compute_daily([])
    text = format_daily(s, "1.05.2026", "en")
    assert "No data" in text


def test_format_daily_includes_counts_and_extra():
    rows = [r(1, "1.05.2026", "won", attempts=3, elapsed_ms=15000)]
    text = format_daily(compute_daily(rows), "1.05.2026", "en")
    assert "1.05.2026" in text
    assert "guessed" in text
    assert "Average attempts" in text


def test_format_daily_no_extra_without_winners():
    rows = [r(1, "1.05.2026", "lost", attempts=6)]
    text = format_daily(compute_daily(rows), "1.05.2026", "en")
    assert "Average attempts" not in text


def test_compute_user_winrate_and_best():
    rows = [
        r(1, "1.05.2026", "won", attempts=3),
        r(1, "2.05.2026", "won", attempts=2),
        r(1, "3.05.2026", "lost", attempts=6),
    ]
    s = compute_user(rows)
    assert s.played == 3
    assert s.wins == 2
    assert s.losses == 1
    assert s.win_rate == 67
    assert s.best_attempts == 2


def test_user_current_and_max_streak():
    rows = [
        r(1, "1.05.2026", "won", attempts=3),
        r(1, "2.05.2026", "won", attempts=3),
        r(1, "3.05.2026", "won", attempts=3),
    ]
    s = compute_user(rows)
    assert s.current_streak == 3
    assert s.max_streak == 3


def test_streak_breaks_on_loss():
    rows = [
        r(1, "1.05.2026", "won", attempts=3),
        r(1, "2.05.2026", "won", attempts=3),
        r(1, "3.05.2026", "lost", attempts=6),
    ]
    s = compute_user(rows)
    assert s.current_streak == 0  # latest day was a loss
    assert s.max_streak == 2


def test_daily_by_lang_breakdown():
    rows = [
        r(1, "1.05.2026", "won", attempts=3, lang="ru"),
        r(2, "1.05.2026", "lost", attempts=6, lang="ru"),
        r(3, "1.05.2026", "won", attempts=2, lang="en"),
        r(4, "1.05.2026", "not_played", lang=""),  # sentinel excluded from by_lang
    ]
    s = compute_daily(rows)
    assert s.by_lang == {"ru": {"won": 1, "lost": 1}, "en": {"won": 1, "lost": 0}}
    text = format_daily(s, "1.05.2026", "en")
    assert "🇷🇺" in text and "🇬🇧" in text


def test_streak_counts_any_language():
    # Won ru on day 1, won en on day 2 -> a 2-day streak regardless of locale.
    rows = [
        r(1, "1.05.2026", "won", attempts=3, lang="ru"),
        r(1, "2.05.2026", "won", attempts=4, lang="en"),
    ]
    s = compute_user(rows)
    assert s.current_streak == 2
    assert s.max_streak == 2


def test_format_user_empty():
    assert "haven't played" in format_user(compute_user([]), "en")


def test_format_duration():
    assert format_duration(15000, "en") == "15s"
    assert format_duration(90000, "en") == "1m 30s"
    assert format_duration(None, "en") == "—"
