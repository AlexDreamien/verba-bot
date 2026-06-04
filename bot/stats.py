"""Pure aggregation and formatting of game results.

Works on lists of :class:`bot.db.Result` (no DB or aiogram), so it is fully
unit-tested. Two views:

* :func:`compute_daily` / :func:`format_daily` — the global summary for one day.
* :func:`compute_user` / :func:`format_user` — one player's history and streaks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from bot.daily import parse_day
from bot.db import Champion, Result, Standing
from bot.i18n import t

__all__ = [
    "DailyStats",
    "UserStats",
    "compute_daily",
    "compute_user",
    "display_name",
    "format_competition",
    "format_daily",
    "format_duration",
    "format_seasons",
    "format_user",
]


# --- daily -----------------------------------------------------------------


LANG_FLAGS = {"ru": "🇷🇺", "uk": "🇺🇦", "en": "🇬🇧"}


@dataclass(frozen=True, slots=True)
class DailyStats:
    total: int
    won: int
    lost: int
    unfinished: int
    not_played: int
    in_progress: int
    avg_attempts: float | None
    avg_elapsed_ms: float | None
    attempts_distribution: dict[int, int] = field(default_factory=dict)
    # Per-locale {lang: {"won": n, "lost": n}} for locales that saw any play.
    by_lang: dict[str, dict[str, int]] = field(default_factory=dict)


def compute_daily(rows: list[Result]) -> DailyStats:
    counts = {"won": 0, "lost": 0, "unfinished": 0, "not_played": 0, "in_progress": 0}
    win_attempts: list[int] = []
    win_times: list[int] = []
    distribution: dict[int, int] = {}
    by_lang: dict[str, dict[str, int]] = {}

    for r in rows:
        if r.status in counts:
            counts[r.status] += 1
        if r.lang and r.status in ("won", "lost"):
            bucket = by_lang.setdefault(r.lang, {"won": 0, "lost": 0})
            bucket[r.status] += 1
        if r.status == "won":
            if r.attempts is not None:
                win_attempts.append(r.attempts)
                distribution[r.attempts] = distribution.get(r.attempts, 0) + 1
            if r.elapsed_ms is not None:
                win_times.append(r.elapsed_ms)

    return DailyStats(
        total=len(rows),
        won=counts["won"],
        lost=counts["lost"],
        unfinished=counts["unfinished"],
        not_played=counts["not_played"],
        in_progress=counts["in_progress"],
        avg_attempts=_mean(win_attempts),
        avg_elapsed_ms=_mean(win_times),
        attempts_distribution=dict(sorted(distribution.items())),
        by_lang=dict(sorted(by_lang.items())),
    )


def format_daily(stats: DailyStats, day: str, lang: str) -> str:
    if stats.total == 0:
        return t("stats_none", lang, day=day)
    extra = ""
    if stats.won > 0:
        avg_attempts = f"{stats.avg_attempts:.1f}" if stats.avg_attempts is not None else "—"
        avg_time = (
            format_duration(stats.avg_elapsed_ms, lang) if stats.avg_elapsed_ms is not None else "—"
        )
        extra = t("stats_extra", lang, avg_attempts=avg_attempts, avg_time=avg_time)
    body = t(
        "stats_body",
        lang,
        total=stats.total,
        won=stats.won,
        lost=stats.lost,
        unfinished=stats.unfinished,
        not_played=stats.not_played,
        extra=extra,
    ).rstrip()
    text = t("stats_title", lang, day=day) + "\n\n" + body
    if stats.by_lang:
        lines = [
            f"{LANG_FLAGS.get(lg, lg)} ✅{c['won']} ❌{c['lost']}"
            for lg, c in stats.by_lang.items()
        ]
        text += "\n\n" + "\n".join(lines)
    return text


# --- per-user --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UserStats:
    played: int
    wins: int
    losses: int
    win_rate: int
    best_attempts: int | None
    avg_attempts: float | None
    current_streak: int
    max_streak: int


def compute_user(rows: list[Result]) -> UserStats:
    wins = [r for r in rows if r.status == "won"]
    losses = [r for r in rows if r.status == "lost"]
    win_attempts = [r.attempts for r in wins if r.attempts is not None]
    played = len(wins) + len(losses)
    win_rate = round(100 * len(wins) / played) if played else 0

    current, longest = _streaks(rows)

    return UserStats(
        played=played,
        wins=len(wins),
        losses=len(losses),
        win_rate=win_rate,
        best_attempts=min(win_attempts) if win_attempts else None,
        avg_attempts=_mean(win_attempts),
        current_streak=current,
        max_streak=longest,
    )


def format_user(stats: UserStats, lang: str) -> str:
    if stats.played == 0:
        return t("me_none", lang)
    best = (
        t("best_attempts", lang, n=stats.best_attempts)
        if stats.best_attempts is not None
        else t("best_none", lang)
    )
    body = t(
        "me_body",
        lang,
        played=stats.played,
        wins=stats.wins,
        losses=stats.losses,
        win_rate=stats.win_rate,
        best=best,
        streak=stats.current_streak,
        max_streak=stats.max_streak,
    )
    return t("me_title", lang) + "\n\n" + body


# --- group ----------------------------------------------------------------


def display_name(first_name: str | None, username: str | None, user_id: int) -> str:
    """A human label for a player: first name, else @username, else #id."""
    if first_name:
        return first_name
    if username:
        return f"@{username}"
    return f"#{user_id}"


_MEDALS = {0: "🥇", 1: "🥈", 2: "🥉"}


def format_competition(standings: list[Standing], season: int, lang: str) -> str:
    """Competition leaderboard for a group's season (points, ✅/❌/💤 counts)."""
    if not standings:
        return t("comp_empty", lang)
    lines = []
    for i, s in enumerate(standings):
        rank = _MEDALS.get(i, f"{i + 1}.")
        name = display_name(s.first_name, s.username, s.user_id)
        avg = f"{s.avg_attempts:.1f}" if s.avg_attempts is not None else "—"
        lines.append(
            t(
                "comp_row",
                lang,
                rank=rank,
                name=name,
                score=s.score,
                wins=s.wins,
                losses=s.losses,
                skips=s.skips,
                avg=avg,
            )
        )
    return (
        t("comp_title", lang, season=season)
        + "\n\n"
        + "\n".join(lines)
        + "\n\n"
        + t("comp_legend", lang)
    )


def format_seasons(champions: list[Champion], lang: str) -> str:
    """Past season champions for a group, most recent first."""
    if not champions:
        return t("seasons_empty", lang)
    lines = [
        t(
            "seasons_row",
            lang,
            season=c.season,
            name=display_name(c.first_name, c.username, c.user_id),
            score=c.score,
        )
        for c in champions
    ]
    return t("seasons_title", lang) + "\n\n" + "\n".join(lines)


# --- helpers ---------------------------------------------------------------


def format_duration(ms: float | None, lang: str) -> str:
    if ms is None:
        return "—"
    total_seconds = round(ms / 1000)
    minutes, seconds = divmod(total_seconds, 60)
    if minutes == 0:
        return t("time_seconds", lang, s=seconds)
    return t("time_minutes", lang, m=minutes, s=seconds)


def _mean(values: list[int]) -> float | None:
    return sum(values) / len(values) if values else None


def _to_date(day: str) -> date | None:
    try:
        year, month, d = parse_day(day)
        return date(year, month, d)
    except (ValueError, TypeError):
        return None


def _streaks(rows: list[Result]) -> tuple[int, int]:
    """Return (current_streak, max_streak) of consecutive won days.

    A calendar day counts as "won" if the user won in *any* locale that day, so
    streaks are language-agnostic. The current streak ends at the most recent
    day the user finished a game (won or lost) and breaks if that day was a loss.
    """
    won_days = {d for d in (_to_date(r.day) for r in rows if r.status == "won") if d}
    played_days = {d for d in (_to_date(r.day) for r in rows if r.status in ("won", "lost")) if d}
    if not won_days:
        return 0, 0

    ordered = sorted(won_days)
    longest = run = 1
    for prev, cur in zip(ordered, ordered[1:], strict=False):
        run = run + 1 if cur - prev == timedelta(days=1) else 1
        longest = max(longest, run)

    current = 0
    cursor = max(played_days)
    while cursor in won_days:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest
