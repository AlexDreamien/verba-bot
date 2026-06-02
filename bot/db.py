"""SQLite-backed storage for users and their daily game results.

Two tables:

* ``users``   — one row per Telegram user (subscription flag, language).
* ``results`` — one row per (user, day), holding the day's outcome.

Result lifecycle for a day::

    (no row)                              -> "not_played"   (set at day close)
    /api/started                          -> "in_progress"
    /api/result {won}                     -> "won"
    /api/result {lost}                    -> "lost"
    "in_progress" still set at day close  -> "unfinished"

``record_result`` is idempotent and never overwrites a terminal result, so a
duplicate report (e.g. the Mini App retrying) is harmless. As in the sibling
reminder-bot, every per-user query is parameterized and filtered by ``user_id``.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

__all__ = ["VerbaDB", "Result", "Status", "User"]

Status = Literal["in_progress", "won", "lost", "unfinished", "not_played"]
TERMINAL: frozenset[str] = frozenset({"won", "lost"})

# Default language for newly-seen users (the bot's default is Ukrainian). Kept
# here (not imported from i18n) so storage stays independent of the message layer.
DEFAULT_USER_LANG = "uk"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
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
"""


@dataclass(frozen=True, slots=True)
class User:
    user_id: int
    username: str | None
    lang: str
    subscribed: bool


@dataclass(frozen=True, slots=True)
class Result:
    user_id: int
    day: str
    status: Status
    attempts: int | None
    elapsed_ms: int | None
    lang: str = ""


class VerbaDB:
    """SQLite-backed store for users and daily results."""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        with closing(self._connect()) as conn, conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- users -------------------------------------------------------------

    def add_user(self, user_id: int, username: str | None = None) -> None:
        """Ensure a user row exists; refresh the cached username on conflict.

        New rows get :data:`DEFAULT_USER_LANG` explicitly (not via the column
        default) so the default language is honoured even on databases created
        before it changed. An existing user's chosen ``lang`` is left untouched.
        """
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO users (user_id, username, lang) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET username = excluded.username",
                (user_id, username, DEFAULT_USER_LANG),
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
    ) -> None:
        """Store a terminal outcome for ``(user, day, lang)``. First terminal write wins."""
        with closing(self._connect()) as conn, conn:
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
