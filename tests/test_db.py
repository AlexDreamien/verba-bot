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
    assert user.lang == "uk"


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


def test_record_result_returns_newly_finalized(db):
    assert db.record_result(1, "1.05.2026", "ru", "won", attempts=3) is True
    # already terminal -> not newly finalized (no double announce)
    assert db.record_result(1, "1.05.2026", "ru", "lost", attempts=6) is False
    assert db.record_result(2, "1.05.2026", "ru", "lost", attempts=6) is True


def test_membership_and_user_groups(db):
    db.track_membership(-100, 1, "alice", "Alice")
    db.track_membership(-100, 2, None, "Bob")
    db.track_membership(-200, 1, "alice", "Alice")
    assert {m.user_id for m in db.group_members(-100)} == {1, 2}
    assert set(db.user_groups(1)) == {-100, -200}
    assert db.user_groups(2) == [-100]


def test_chat_lang_default_and_set(db):
    assert db.get_chat_lang(-100) == "uk"  # default
    db.set_chat_lang(-100, "en")
    assert db.get_chat_lang(-100) == "en"


def test_daily_rows_for_users(db):
    db.record_result(1, "1.05.2026", "ru", "won", attempts=2)
    db.record_result(2, "1.05.2026", "ru", "lost", attempts=6)
    db.record_result(3, "1.05.2026", "ru", "won", attempts=4)
    rows = db.daily_rows_for_users("1.05.2026", [1, 2])
    assert {row.user_id for row in rows} == {1, 2}
    assert db.daily_rows_for_users("1.05.2026", []) == []


def test_register_is_idempotent(db):
    assert db.register(-100, 1) is True
    assert db.register(-100, 1) is False  # already registered
    assert db.register(-200, 1) is True  # separate per group
    assert db.is_registered(-100, 1) is True
    assert db.is_registered(-300, 1) is False


def test_credit_competition_first_and_subsequent(db):
    db.add_user(1, "alice", "Alice")
    db.add_user(2, "bob", "Bob")
    db.register(-100, 1)
    db.register(-100, 2)

    # First winner of the (day, uk) round in this group: +3 and announced.
    assert db.credit_competition(1, "1.05.2026", "uk", "won") == [-100]
    # Second winner same round: +1, not announced.
    assert db.credit_competition(2, "1.05.2026", "uk", "won") == []

    standings = {s.user_id: s for s in db.competition_standings(-100)}
    assert standings[1].score == 3
    assert standings[2].score == 1
    assert standings[1].wins == 1 and standings[2].wins == 1


def test_credit_competition_per_language(db):
    db.register(-100, 1)
    assert db.credit_competition(1, "1.05.2026", "uk", "won") == [-100]
    # A different language is a separate round -> first again.
    assert db.credit_competition(1, "1.05.2026", "en", "won") == [-100]
    assert db.competition_standings(-100)[0].score == 6  # 3 + 3


def test_credit_competition_loss_and_unregistered(db):
    db.register(-100, 1)
    assert db.credit_competition(1, "1.05.2026", "uk", "lost") == []  # loss, no announce
    # Unregistered user earns nothing and triggers no announcement.
    assert db.credit_competition(2, "1.05.2026", "uk", "won") == []
    s1 = db.competition_standings(-100)[0]
    assert s1.losses == 1 and s1.score == 0
    assert db.competition_standings(-200) == []  # no registrations there


def test_close_competition_marks_skips(db):
    db.register(-100, 1)
    db.credit_competition(1, "1.05.2026", "uk", "won")  # plays uk only
    db.close_competition("1.05.2026")
    s = db.competition_standings(-100)[0]
    assert s.wins == 1
    assert s.skips == 2  # ru + en unplayed -> skipped; uk untouched
    assert s.score == 3


def test_competition_standings_orders_by_score(db):
    db.add_user(1, None, "Alice")
    db.add_user(2, None, "Bob")
    db.register(-100, 1)
    db.register(-100, 2)
    db.credit_competition(2, "1.05.2026", "uk", "won")  # Bob first: 3
    db.credit_competition(1, "1.05.2026", "uk", "won")  # Alice second: 1
    db.credit_competition(1, "2.05.2026", "uk", "won")  # Alice first: 3 -> total 4
    order = [s.user_id for s in db.competition_standings(-100)]
    assert order == [1, 2]  # Alice 4 pts ahead of Bob 3 pts


def test_unregister(db):
    db.register(-100, 1)
    db.credit_competition(1, "1.05.2026", "uk", "won")
    assert db.unregister(-100, 1) is True
    assert db.unregister(-100, 1) is False  # already gone
    assert db.competition_standings(-100) == []  # leaves the leaderboard
    # Rejoining surfaces the preserved history again.
    db.register(-100, 1)
    assert db.competition_standings(-100)[0].score == 3


def test_seasons_default_and_lifecycle(db):
    assert db.get_season(-100) == (1, True)  # implicit season 1, active
    # Can't start while a season is running.
    assert db.start_season(-100) is None
    assert db.finish_season(-100) == 1
    assert db.get_season(-100) == (1, False)
    # Now a new season can begin.
    assert db.start_season(-100) == 2
    assert db.get_season(-100) == (2, True)
    assert db.finish_season(-100) == 2
    assert db.finish_season(-100) is None  # nothing active


def test_points_scoped_to_season(db):
    db.register(-100, 1)
    db.credit_competition(1, "1.05.2026", "uk", "won")  # season 1: +3
    assert db.competition_standings(-100)[0].score == 3
    # New season resets the visible leaderboard.
    db.finish_season(-100)
    db.start_season(-100)  # -> season 2
    assert db.competition_standings(-100)[0].score == 0
    db.credit_competition(1, "2.05.2026", "uk", "won")  # season 2: +3
    assert db.competition_standings(-100)[0].score == 3


def test_no_points_while_season_inactive(db):
    db.register(-100, 1)
    db.finish_season(-100)  # season 1 closed, none active
    assert db.credit_competition(1, "1.05.2026", "uk", "won") == []  # paused: no announce
    assert db.competition_standings(-100)[0].score == 0


def test_first_win_resets_each_season(db):
    db.register(-100, 1)
    db.register(-100, 2)
    assert db.credit_competition(1, "1.05.2026", "uk", "won") == [-100]  # season 1 first
    db.finish_season(-100)
    db.start_season(-100)  # season 2
    # Same round key, new season -> first-win bonus available again.
    assert db.credit_competition(2, "1.05.2026", "uk", "won") == [-100]


def test_user_history(db):
    db.record_result(1, "1.05.2026", "ru", "won", attempts=3)
    db.record_result(1, "2.05.2026", "ru", "lost", attempts=6)
    history = db.user_history(1)
    assert len(history) == 2
    days = {r.day for r in history}
    assert days == {"1.05.2026", "2.05.2026"}
