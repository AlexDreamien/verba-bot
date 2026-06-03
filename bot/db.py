"""SQLite-backed storage for users, daily results, and group memberships.

Tables:

* ``users``       — one row per Telegram user (subscription flag, language, name).
* ``results``     — one row per (user, day, lang), holding the day's outcome.
* ``memberships`` — which users the bot has seen in which group chats (for group
  stats and win announcements). A normal bot can't enumerate group members, so
  this records users who interact in the group (and all senders if privacy mode
  is disabled).
* ``chats``       — per-group settings (title, language).

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

__all__ = ["VerbaDB", "Member", "Result", "Status", "User"]

Status = Literal["in_progress", "won", "lost", "unfinished", "not_played"]
TERMINAL: frozenset[str] = frozenset({"won", "lost"})

# Default language for newly-seen users/chats (the bot's default is Ukrainian).
# Kept here (not imported from i18n) so storage stays independent of messages.
DEFAULT_USER_LANG = "uk"

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
    chat_id INTEGER PRIMARY KEY,
    title   TEXT,
    lang    TEXT NOT NULL DEFAULT 'uk'
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
        """Add columns missing on databases created by older versions."""
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
        if "first_name" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN first_name TEXT")

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
