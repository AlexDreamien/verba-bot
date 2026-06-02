"""Tests for the SQLite store: users, results, idempotency, day close."""

from __future__ import annotations

import pytest

from bot.db import VerbaDB


@pytest.fixture()
def db(tmp_path):
    return VerbaDB(tmp_path / "test.db")


def test_add_and_get_user(db):
    db.add_user(1, "alice")
    user = db.get_user(1)
    assert user is not None
    assert user.username == "alice"
    assert user.subscribed is True  # default
    assert user.lang == "ru"


def test_add_user_refreshes_username(db):
    db.add_user(1, "alice")
    db.add_user(1, "alice2")
    assert db.get_user(1).username == "alice2"


def test_subscription_toggle(db):
    db.add_user(1, "alice")
    db.set_subscribed(1, False)
    assert db.get_user(1).subscribed is False
    assert db.subscriber_ids() == []
    db.set_subscribed(1, True)
    assert db.subscriber_ids() == [1]


def test_list_subscribers_excludes_unsubscribed(db):
    db.add_user(1, "a")
    db.add_user(2, "b")
    db.set_subscribed(2, False)
    assert [u.user_id for u in db.list_subscribers()] == [1]


def test_set_lang(db):
    db.add_user(1, "a")
    db.set_lang(1, "en")
    assert db.get_user(1).lang == "en"


def test_start_then_record(db):
    db.start_result(1, "1.05.2026", "ru")
    assert db.get_result(1, "1.05.2026", "ru").status == "in_progress"
    db.record_result(1, "1.05.2026", "ru", "won", attempts=3, elapsed_ms=42000)
    r = db.get_result(1, "1.05.2026", "ru")
    assert r.status == "won"
    assert r.attempts == 3
    assert r.elapsed_ms == 42000
    assert r.lang == "ru"


def test_record_result_is_idempotent(db):
    db.record_result(1, "1.05.2026", "ru", "won", attempts=2)
    # A duplicate/later report must not overwrite a terminal result.
    db.record_result(1, "1.05.2026", "ru", "lost", attempts=6)
    r = db.get_result(1, "1.05.2026", "ru")
    assert r.status == "won"
    assert r.attempts == 2


def test_start_does_not_overwrite_terminal(db):
    db.record_result(1, "1.05.2026", "ru", "won", attempts=2)
    db.start_result(1, "1.05.2026", "ru")
    assert db.get_result(1, "1.05.2026", "ru").status == "won"


def test_languages_are_independent(db):
    day = "1.05.2026"
    db.record_result(1, day, "ru", "won", attempts=2)
    db.record_result(1, day, "en", "lost", attempts=6)
    assert db.get_result(1, day, "ru").status == "won"
    assert db.get_result(1, day, "en").status == "lost"
    assert len(db.daily_rows(day)) == 2


def test_close_day_marks_unfinished_and_not_played(db):
    day = "1.05.2026"
    db.add_user(1, "winner")
    db.add_user(2, "midgame")
    db.add_user(3, "noshow")
    db.record_result(1, day, "ru", "won", attempts=4)
    db.start_result(2, day, "uk")  # in_progress

    db.close_day(day, [1, 2, 3])

    assert db.get_result(1, day, "ru").status == "won"  # terminal untouched
    assert db.get_result(2, day, "uk").status == "unfinished"
    # A user who played nothing gets a single not_played row (sentinel lang '').
    assert db.get_result(3, day, "").status == "not_played"


def test_close_day_skips_users_who_played(db):
    day = "1.05.2026"
    db.record_result(1, day, "en", "lost", attempts=6)
    db.close_day(day, [1])
    # User 1 played (and lost) — must not also get a not_played row.
    assert db.get_result(1, day, "") is None


def test_user_history(db):
    db.record_result(1, "1.05.2026", "ru", "won", attempts=3)
    db.record_result(1, "2.05.2026", "ru", "lost", attempts=6)
    history = db.user_history(1)
    assert len(history) == 2
    days = {r.day for r in history}
    assert days == {"1.05.2026", "2.05.2026"}
