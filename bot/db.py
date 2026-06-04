"""SQLite-backed storage for users, daily results, and group memberships.

Tables:

* ``users``       — one row per Telegram user (subscription flag, language, name).
* ``results``     — one row per (user, day, lang), holding the day's outcome.
* ``memberships`` — which users the bot has seen in which group chats. A normal
  bot can't enumerate group members, so this records users who interact in the
  group (and all senders if privacy mode is disabled).
* ``chats``       — per-group settings (title, language, current season number
  and whether a season is active).
* ``registrations`` — explicit opt-in to a group's competition: one row per
  (chat, user). A user must ``/register`` separately in each group.
* ``competition`` — one row per (chat, user, day, lang) round for registered
  players: outcome (won/lost/skipped), points, and whether it was the first win
  in that group's round.
* ``competition_first`` — the first winner per (chat, season, day, lang); used to
  award the first-guess bonus and announce exactly one winner per round.
* ``season_history`` — the champion of each finished season per group.

A "round" is a single (day, language) — there are three words per day, and a
player scores in each language independently. Scoring (see :func:`win_points`):
a win earns ``max(1, 7 - attempts)`` (a 1-guess solve = 6 … a 6-guess solve = 1),
plus ``FIRST_BONUS`` for being the first in the group to win that round. Skips
are counted only for languages a player has joined (won/lost at least once this
season); an unfinished or unplayed *joined* round becomes a skip at day close.

Each group runs in **seasons** (``chats.season``, default 1, active by default).
Competition rows are tagged with the season they were earned in, and the
leaderboard shows only the current season — so a new season resets the standings
while preserving history. Admins manage seasons with ``/startseason`` and
``/finishseason``; while no season is active (after a finish, before the next
start) results are still recorded personally but earn no competition points.

Result lifecycle for a day::

    (no row)                              -> "not_played"   (set at day close)
    /api/started                          -> "in_progress"
    /api/result {won}                     -> "won"
    /api/result {lost}                    -> "lost"
    "in_progress" still set at day close  -> "unfinished"

``record_result`` is idempotent and never overwrites a terminal result. Every
per-user query is parameterized and filtered by ``user_id``.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

__all__ = ["VerbaDB", "Champion", "Member", "Result", "Standing", "Status", "User", "win_points"]

Status = Literal["in_progress", "won", "lost", "unfinished", "not_played"]
TERMINAL: frozenset[str] = frozenset({"won", "lost"})

# Default language for newly-seen users/chats (the bot's default is Ukrainian).
# Kept here (not imported from i18n) so storage stays independent of messages.
DEFAULT_USER_LANG = "uk"

# The three daily rounds. Kept here (not imported from i18n) so storage stays
# self-contained; close_competition marks a skip for each unplayed language.
COMP_LANGS: tuple[str, ...] = ("uk", "ru", "en")

# Competition scoring. A win is worth more the fewer guesses it took
# (max(1, 7 - attempts): a 1-guess solve = 6, a 6-guess solve = 1), plus a
# FIRST_BONUS for being the first registered player to win a group's round.
MAX_GUESSES = 6
FIRST_BONUS = 3


def win_points(attempts: int | None, is_first: bool) -> int:
    """Points for a winning round: efficiency base + optional first-win bonus."""
    base = max(1, (MAX_GUESSES + 1) - (attempts or MAX_GUESSES))
    return base + (FIRST_BONUS if is_first else 0)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    first_name TEXT,
    lang       TEXT NOT NULL DEFAULT 'uk',
    subscribed INTEGER NOT NULL DEFAULT 1,
    joined_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS results (
    user_id    INTEGER NOT NULL,
    day        TEXT NOT NULL,
    lang       TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL,
    attempts   INTEGER,
    elapsed_ms INTEGER,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, day, lang)
);
CREATE INDEX IF NOT EXISTS idx_results_day ON results(day);

CREATE TABLE IF NOT EXISTS memberships (
    chat_id    INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    username   TEXT,
    first_name TEXT,
    PRIMARY KEY (chat_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id);

CREATE TABLE IF NOT EXISTS chats (
    chat_id       INTEGER PRIMARY KEY,
    title         TEXT,
    lang          TEXT NOT NULL DEFAULT 'uk',
    season        INTEGER NOT NULL DEFAULT 1,
    season_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS registrations (
    chat_id   INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (chat_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_registrations_user ON registrations(user_id);

CREATE TABLE IF NOT EXISTS competition (
    chat_id  INTEGER NOT NULL,
    user_id  INTEGER NOT NULL,
    day      TEXT NOT NULL,
    lang     TEXT NOT NULL,
    season   INTEGER NOT NULL DEFAULT 1,
    status   TEXT NOT NULL,            -- 'won' | 'lost' | 'skipped'
    points   INTEGER NOT NULL DEFAULT 0,
    is_first INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER,                  -- guesses used on a win (for tie-breaks)
    PRIMARY KEY (chat_id, user_id, day, lang)
);
CREATE INDEX IF NOT EXISTS idx_competition_round ON competition(chat_id, season, day, lang);

CREATE TABLE IF NOT EXISTS competition_first (
    chat_id INTEGER NOT NULL,
    season  INTEGER NOT NULL,
    day     TEXT NOT NULL,
    lang    TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (chat_id, season, day, lang)
);

CREATE TABLE IF NOT EXISTS season_history (
    chat_id     INTEGER NOT NULL,
    season      INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,      -- the champion (top of the leaderboard)
    score       INTEGER NOT NULL,
    finished_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (chat_id, season)
);
"""


@dataclass(frozen=True, slots=True)
class User:
    user_id: int
    username: str | None
    first_name: str | None
    lang: str
    subscribed: bool


@dataclass(frozen=True, slots=True)
class Member:
    user_id: int
    username: str | None
    first_name: str | None


@dataclass(frozen=True, slots=True)
class Standing:
    """One registered player's standing in a group's current season."""

    user_id: int
    username: str | None
    first_name: str | None
    score: int
    wins: int
    losses: int
    skips: int
    avg_attempts: float | None


@dataclass(frozen=True, slots=True)
class Champion:
    """The winner of a finished season in a group."""

    season: int
    user_id: int
    username: str | None
    first_name: str | None
    score: int


@dataclass(frozen=True, slots=True)
class Result:
    user_id: int
    day: str
    status: Status
    attempts: int | None
    elapsed_ms: int | None
    lang: str = ""


class VerbaDB:
    """SQLite-backed store for users, results, and group memberships."""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        with closing(self._connect()) as conn, conn:
            conn.executescript(_SCHEMA)
            self._migrate(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Add columns/tables missing on databases created by older versions."""
        user_cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
        if "first_name" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN first_name TEXT")

        chat_cols = {r["name"] for r in conn.execute("PRAGMA table_info(chats)")}
        if chat_cols and "season" not in chat_cols:
            conn.execute("ALTER TABLE chats ADD COLUMN season INTEGER NOT NULL DEFAULT 1")
        if chat_cols and "season_active" not in chat_cols:
            conn.execute("ALTER TABLE chats ADD COLUMN season_active INTEGER NOT NULL DEFAULT 1")

        comp_cols = {r["name"] for r in conn.execute("PRAGMA table_info(competition)")}
        if comp_cols and "season" not in comp_cols:
            conn.execute("ALTER TABLE competition ADD COLUMN season INTEGER NOT NULL DEFAULT 1")
        if comp_cols and "attempts" not in comp_cols:
            conn.execute("ALTER TABLE competition ADD COLUMN attempts INTEGER")

        # competition_first gained ``season`` in its PRIMARY KEY; SQLite can't alter
        # a PK in place, so recreate it (it only holds the current day's first-win
        # dedup markers, which are safe to drop).
        first_cols = {r["name"] for r in conn.execute("PRAGMA table_info(competition_first)")}
        if first_cols and "season" not in first_cols:
            conn.execute("DROP TABLE competition_first")
            conn.execute(
                "CREATE TABLE competition_first ("
                "    chat_id INTEGER NOT NULL, season INTEGER NOT NULL, "
                "    day TEXT NOT NULL, lang TEXT NOT NULL, user_id INTEGER NOT NULL, "
                "    PRIMARY KEY (chat_id, season, day, lang))"
            )

    # -- users -------------------------------------------------------------

    def add_user(
        self, user_id: int, username: str | None = None, first_name: str | None = None
    ) -> None:
        """Ensure a user row exists; refresh cached username/first_name on conflict.

        New rows get :data:`DEFAULT_USER_LANG` explicitly (not via the column
        default) so the default language is honoured even on databases created
        before it changed. An existing user's chosen ``lang`` is left untouched.
        """
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO users (user_id, username, first_name, lang) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "    username = excluded.username, first_name = excluded.first_name",
                (user_id, username, first_name, DEFAULT_USER_LANG),
            )

    def set_subscribed(self, user_id: int, subscribed: bool) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE users SET subscribed = ? WHERE user_id = ?",
                (1 if subscribed else 0, user_id),
            )

    def set_lang(self, user_id: int, lang: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))

    def get_user(self, user_id: int) -> User | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return _row_to_user(row) if row else None

    def list_subscribers(self) -> list[User]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM users WHERE subscribed = 1 ORDER BY user_id"
            ).fetchall()
        return [_row_to_user(r) for r in rows]

    def subscriber_ids(self) -> list[int]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT user_id FROM users WHERE subscribed = 1").fetchall()
        return [int(r["user_id"]) for r in rows]

    # -- group memberships & chats ----------------------------------------

    def track_membership(
        self, chat_id: int, user_id: int, username: str | None, first_name: str | None
    ) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO memberships (chat_id, user_id, username, first_name) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(chat_id, user_id) DO UPDATE SET "
                "    username = excluded.username, first_name = excluded.first_name",
                (chat_id, user_id, username, first_name),
            )

    def group_members(self, chat_id: int) -> list[Member]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT user_id, username, first_name FROM memberships WHERE chat_id = ? "
                "ORDER BY first_name, user_id",
                (chat_id,),
            ).fetchall()
        return [Member(r["user_id"], r["username"], r["first_name"]) for r in rows]

    def user_groups(self, user_id: int) -> list[int]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT chat_id FROM memberships WHERE user_id = ?", (user_id,)
            ).fetchall()
        return [int(r["chat_id"]) for r in rows]

    def upsert_chat(self, chat_id: int, title: str | None = None) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO chats (chat_id, title) VALUES (?, ?) "
                "ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title",
                (chat_id, title),
            )

    def get_chat_lang(self, chat_id: int) -> str:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT lang FROM chats WHERE chat_id = ?", (chat_id,)).fetchone()
        return row["lang"] if row else DEFAULT_USER_LANG

    def set_chat_lang(self, chat_id: int, lang: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO chats (chat_id, lang) VALUES (?, ?) "
                "ON CONFLICT(chat_id) DO UPDATE SET lang = excluded.lang",
                (chat_id, lang),
            )

    # Tables keyed by chat_id, remapped when a group migrates to a supergroup.
    _CHAT_TABLES = (
        "registrations",
        "chats",
        "competition",
        "competition_first",
        "season_history",
        "memberships",
    )

    def migrate_chat(self, old_id: int, new_id: int) -> None:
        """Move all data from ``old_id`` to ``new_id`` (group → supergroup upgrade).

        Telegram changes a group's id on upgrade; without this, announcements and
        the leaderboard would target the dead id. ``UPDATE OR IGNORE`` then a
        cleanup delete keeps any pre-existing rows under the new id.
        """
        with closing(self._connect()) as conn, conn:
            for table in self._CHAT_TABLES:
                conn.execute(
                    f"UPDATE OR IGNORE {table} SET chat_id = ? WHERE chat_id = ?",  # noqa: S608
                    (new_id, old_id),
                )
                conn.execute(f"DELETE FROM {table} WHERE chat_id = ?", (old_id,))  # noqa: S608

    # -- competition (per-group, opt-in) ----------------------------------

    def register(self, chat_id: int, user_id: int) -> bool:
        """Opt a user into a group's competition. Returns True if newly added."""
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO registrations (chat_id, user_id) VALUES (?, ?)",
                (chat_id, user_id),
            )
        return cur.rowcount > 0

    def is_registered(self, chat_id: int, user_id: int) -> bool:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT 1 FROM registrations WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            ).fetchone()
        return row is not None

    def unregister(self, chat_id: int, user_id: int) -> bool:
        """Leave a group's competition. Returns True if the user was registered.

        Past competition rows are kept (history) but no longer surface in the
        leaderboard, which is filtered through ``registrations``.
        """
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "DELETE FROM registrations WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
        return cur.rowcount > 0

    def get_season(self, chat_id: int) -> tuple[int, bool]:
        """Return ``(season_number, is_active)``; defaults to season 1, active."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT season, season_active FROM chats WHERE chat_id = ?", (chat_id,)
            ).fetchone()
        if row is None:
            return (1, True)
        return (int(row["season"]), bool(row["season_active"]))

    def start_season(self, chat_id: int) -> int | None:
        """Begin the next season (resetting the leaderboard). Returns the new
        season number, or ``None`` if a season is already running."""
        with closing(self._connect()) as conn, conn:
            season, active = self._season_row(conn, chat_id)
            if active:
                return None
            new_season = season + 1
            conn.execute(
                "INSERT INTO chats (chat_id, season, season_active) VALUES (?, ?, 1) "
                "ON CONFLICT(chat_id) DO UPDATE SET season = excluded.season, season_active = 1",
                (chat_id, new_season),
            )
            return new_season

    def finish_season(self, chat_id: int) -> int | None:
        """Close the running season. Returns the finished season number, or
        ``None`` if no season was active."""
        with closing(self._connect()) as conn, conn:
            season, active = self._season_row(conn, chat_id)
            if not active:
                return None
            conn.execute(
                "INSERT INTO chats (chat_id, season, season_active) VALUES (?, ?, 0) "
                "ON CONFLICT(chat_id) DO UPDATE SET season_active = 0",
                (chat_id, season),
            )
            return season

    @staticmethod
    def _season_row(conn: sqlite3.Connection, chat_id: int) -> tuple[int, bool]:
        row = conn.execute(
            "SELECT season, season_active FROM chats WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        if row is None:
            return (1, True)
        return (int(row["season"]), bool(row["season_active"]))

    def credit_competition(
        self, user_id: int, day: str, lang: str, status: Status, attempts: int | None = None
    ) -> list[int]:
        """Attribute a terminal round result to every group the user is registered in.

        Awards points via :func:`win_points` (efficiency base + first-win bonus; a
        loss is 0) and returns the chat ids where this user was the *first* to win
        the round — i.e. the chats to announce to. Groups whose season is inactive
        are skipped (no points). Idempotent: an already-finalized row is untouched.
        """
        if status not in TERMINAL:
            return []
        announce: list[int] = []
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                "SELECT r.chat_id AS chat_id, "
                "       COALESCE(ch.season, 1) AS season, "
                "       COALESCE(ch.season_active, 1) AS active "
                "FROM registrations r LEFT JOIN chats ch ON ch.chat_id = r.chat_id "
                "WHERE r.user_id = ?",
                (user_id,),
            ).fetchall()
            for row in rows:
                if not row["active"]:
                    continue  # competition paused between seasons -> no points
                chat_id, season = int(row["chat_id"]), int(row["season"])
                is_first = False
                if status == "won":
                    cur = conn.execute(
                        "INSERT OR IGNORE INTO competition_first "
                        "    (chat_id, season, day, lang, user_id) VALUES (?, ?, ?, ?, ?)",
                        (chat_id, season, day, lang, user_id),
                    )
                    is_first = cur.rowcount == 1
                points = win_points(attempts, is_first) if status == "won" else 0
                won_attempts = attempts if status == "won" else None
                conn.execute(
                    "INSERT INTO competition "
                    "    (chat_id, user_id, day, lang, season, status, points, is_first, attempts) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(chat_id, user_id, day, lang) DO UPDATE SET "
                    "    season = excluded.season, status = excluded.status, "
                    "    points = excluded.points, is_first = excluded.is_first, "
                    "    attempts = excluded.attempts "
                    "WHERE competition.status NOT IN ('won', 'lost')",
                    (
                        chat_id,
                        user_id,
                        day,
                        lang,
                        season,
                        status,
                        points,
                        1 if is_first else 0,
                        won_attempts,
                    ),
                )
                if is_first:
                    announce.append(chat_id)
        return announce

    def close_competition(self, day: str) -> None:
        """Mark a skip for each round a player *opted into* but didn't finish.

        A player opts into a language by winning or losing it at least once in the
        current season; only those languages can accrue skips — so someone who
        plays a single language is never penalised for the other two. Active
        seasons only; a round already played today won't be overwritten.
        """
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO competition (chat_id, user_id, day, lang, season, status) "
                "SELECT r.chat_id, r.user_id, ?, c.lang, COALESCE(ch.season, 1), 'skipped' "
                "FROM registrations r "
                "LEFT JOIN chats ch ON ch.chat_id = r.chat_id "
                "JOIN competition c "
                "  ON c.chat_id = r.chat_id AND c.user_id = r.user_id "
                " AND c.season = COALESCE(ch.season, 1) AND c.status IN ('won', 'lost') "
                "WHERE COALESCE(ch.season_active, 1) = 1 "
                "GROUP BY r.chat_id, r.user_id, c.lang "
                "ON CONFLICT(chat_id, user_id, day, lang) DO NOTHING",
                (day,),
            )

    def competition_standings(self, chat_id: int) -> list[Standing]:
        """Leaderboard for a group's *current* season: every registered player, ranked."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT r.user_id AS user_id, u.username AS username, "
                "       u.first_name AS first_name, "
                "       COALESCE(SUM(c.points), 0) AS score, "
                "       COALESCE(SUM(c.status = 'won'), 0) AS wins, "
                "       COALESCE(SUM(c.status = 'lost'), 0) AS losses, "
                "       COALESCE(SUM(c.status = 'skipped'), 0) AS skips, "
                "       AVG(CASE WHEN c.status = 'won' THEN c.attempts END) AS avg_attempts "
                "FROM registrations r "
                "LEFT JOIN competition c "
                "       ON c.chat_id = r.chat_id AND c.user_id = r.user_id "
                "      AND c.season = COALESCE("
                "              (SELECT season FROM chats WHERE chat_id = r.chat_id), 1) "
                "LEFT JOIN users u ON u.user_id = r.user_id "
                "WHERE r.chat_id = ? "
                "GROUP BY r.user_id "
                "ORDER BY score DESC, wins DESC, "
                "         avg_attempts IS NULL, avg_attempts ASC, first_name, r.user_id",
                (chat_id,),
            ).fetchall()
        return [
            Standing(
                user_id=int(r["user_id"]),
                username=r["username"],
                first_name=r["first_name"],
                score=int(r["score"]),
                wins=int(r["wins"]),
                losses=int(r["losses"]),
                skips=int(r["skips"]),
                avg_attempts=float(r["avg_attempts"]) if r["avg_attempts"] is not None else None,
            )
            for r in rows
        ]

    def record_champion(self, chat_id: int, season: int, user_id: int, score: int) -> None:
        """Store the winner of a finished season (no-op if already recorded)."""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO season_history (chat_id, season, user_id, score) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(chat_id, season) DO NOTHING",
                (chat_id, season, user_id, score),
            )

    def season_history(self, chat_id: int) -> list[Champion]:
        """Past season champions for a group, most recent first."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT h.season AS season, h.user_id AS user_id, h.score AS score, "
                "       u.username AS username, u.first_name AS first_name "
                "FROM season_history h LEFT JOIN users u ON u.user_id = h.user_id "
                "WHERE h.chat_id = ? ORDER BY h.season DESC",
                (chat_id,),
            ).fetchall()
        return [
            Champion(
                season=int(r["season"]),
                user_id=int(r["user_id"]),
                username=r["username"],
                first_name=r["first_name"],
                score=int(r["score"]),
            )
            for r in rows
        ]

    # -- results -----------------------------------------------------------

    def start_result(self, user_id: int, day: str, lang: str) -> None:
        """Mark that the user opened the game for ``lang`` today (no-op if a row exists)."""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO results (user_id, day, lang, status) VALUES (?, ?, ?, 'in_progress') "
                "ON CONFLICT(user_id, day, lang) DO NOTHING",
                (user_id, day, lang),
            )

    def record_result(
        self,
        user_id: int,
        day: str,
        lang: str,
        status: Status,
        attempts: int | None = None,
        elapsed_ms: int | None = None,
    ) -> bool:
        """Store a terminal outcome for ``(user, day, lang)``.

        Returns ``True`` only if this call newly finalized the game (the row was
        not already won/lost) — used to announce a win exactly once.
        """
        with closing(self._connect()) as conn, conn:
            existing = conn.execute(
                "SELECT status FROM results WHERE user_id = ? AND day = ? AND lang = ?",
                (user_id, day, lang),
            ).fetchone()
            if existing and existing["status"] in TERMINAL:
                return False
            conn.execute(
                "INSERT INTO results (user_id, day, lang, status, attempts, elapsed_ms) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, day, lang) DO UPDATE SET "
                "    status = excluded.status, "
                "    attempts = excluded.attempts, "
                "    elapsed_ms = excluded.elapsed_ms, "
                "    updated_at = datetime('now') "
                "WHERE results.status NOT IN ('won', 'lost')",
                (user_id, day, lang, status, attempts, elapsed_ms),
            )
        return status in TERMINAL

    def close_day(self, day: str, subscriber_ids: list[int]) -> None:
        """Finalize a day: in_progress -> unfinished; subscribers who played no
        locale at all -> a single ``not_played`` row (sentinel ``lang = ''``)."""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE results SET status = 'unfinished', updated_at = datetime('now') "
                "WHERE day = ? AND status = 'in_progress'",
                (day,),
            )
            played = {
                int(r["user_id"])
                for r in conn.execute(
                    "SELECT DISTINCT user_id FROM results WHERE day = ?", (day,)
                ).fetchall()
            }
            missing = [uid for uid in subscriber_ids if uid not in played]
            conn.executemany(
                "INSERT INTO results (user_id, day, lang, status) VALUES (?, ?, '', 'not_played') "
                "ON CONFLICT(user_id, day, lang) DO NOTHING",
                [(uid, day) for uid in missing],
            )

    def get_result(self, user_id: int, day: str, lang: str) -> Result | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM results WHERE user_id = ? AND day = ? AND lang = ?",
                (user_id, day, lang),
            ).fetchone()
        return _row_to_result(row) if row else None

    def daily_rows(self, day: str) -> list[Result]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM results WHERE day = ?", (day,)).fetchall()
        return [_row_to_result(r) for r in rows]

    def daily_rows_for_users(self, day: str, user_ids: list[int]) -> list[Result]:
        if not user_ids:
            return []
        placeholders = ",".join("?" for _ in user_ids)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT * FROM results WHERE day = ? AND user_id IN ({placeholders})",
                (day, *user_ids),
            ).fetchall()
        return [_row_to_result(r) for r in rows]

    def user_history(self, user_id: int, limit: int | None = None) -> list[Result]:
        sql = "SELECT * FROM results WHERE user_id = ? ORDER BY updated_at DESC"
        params: tuple[object, ...] = (user_id,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (user_id, limit)
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_result(r) for r in rows]


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        user_id=row["user_id"],
        username=row["username"],
        first_name=row["first_name"],
        lang=row["lang"],
        subscribed=bool(row["subscribed"]),
    )


def _row_to_result(row: sqlite3.Row) -> Result:
    return Result(
        user_id=row["user_id"],
        day=row["day"],
        status=row["status"],
        attempts=row["attempts"],
        elapsed_ms=row["elapsed_ms"],
        lang=row["lang"],
    )
