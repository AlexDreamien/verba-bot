"""Daily-word helpers.

The engine keys each day by the date in Kyiv time formatted as ``"d.mm.yyyy"``
— day NOT zero-padded, month zero-padded (e.g. ``"1.05.2026"``, ``"20.03.2022"``)
— matching ``engine.js``'s ``dayKey``.

The Mini App reports results tagged with that exact key, so the backend must
produce an identical string when it closes a day. ``day_key`` is the single
source of truth for that format and is kept aligned with the engine.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

__all__ = ["DEFAULT_TZ", "day_key", "parse_day"]

DEFAULT_TZ = "Europe/Kyiv"


def day_key(now: datetime, tz: str = DEFAULT_TZ) -> str:
    """Return the game's day key for ``now`` rendered in timezone ``tz``.

    ``now`` may be naive (interpreted as UTC by the caller's convention) or
    timezone-aware; it is converted to ``tz`` before formatting.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("UTC"))
    local = now.astimezone(ZoneInfo(tz))
    return f"{local.day}.{local.month:02d}.{local.year}"


def parse_day(key: str) -> tuple[int, int, int]:
    """Parse a ``"d.mm.yyyy"`` day key into ``(year, month, day)``.

    Raises ``ValueError`` on a malformed key.
    """
    parts = key.split(".")
    if len(parts) != 3:
        raise ValueError(f"malformed day key: {key!r}")
    day, month, year = (int(p) for p in parts)
    return year, month, day
