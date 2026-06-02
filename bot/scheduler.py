"""APScheduler wrapper for the two recurring jobs.

* daily broadcast — sends the game link to all subscribers (cron, optional);
* day close — at ``CLOSE_DAY_AT`` finalizes the day (unfinished / not_played)
  and triggers the end-of-day summary.

The scheduler owns no domain logic: it just maps triggers to the async
callbacks it is given. Times run in the configured timezone.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

__all__ = ["VerbaScheduler", "parse_hh_mm"]

log = logging.getLogger(__name__)

AsyncJob = Callable[[], Awaitable[None]]


def parse_hh_mm(value: str) -> tuple[int, int]:
    """Parse ``"HH:MM"`` into ``(hour, minute)``; raises ``ValueError`` if bad."""
    hour_s, minute_s = value.split(":")
    hour, minute = int(hour_s), int(minute_s)
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError(f"invalid time of day: {value!r}")
    return hour, minute


class VerbaScheduler:
    def __init__(self, timezone: str) -> None:
        self._scheduler = AsyncIOScheduler(timezone=timezone)
        self._tz = timezone

    def start(self) -> None:
        self._scheduler.start()

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    def add_broadcast(self, cron: str, job: AsyncJob) -> None:
        """Schedule the daily broadcast from a crontab expression."""
        self._scheduler.add_job(
            job,
            trigger=CronTrigger.from_crontab(cron, timezone=self._tz),
            id="daily-broadcast",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        log.info("Scheduled daily broadcast: %s (%s)", cron, self._tz)

    def add_close_day(self, hh_mm: str, job: AsyncJob) -> None:
        """Schedule the end-of-day close at ``HH:MM`` local time."""
        hour, minute = parse_hh_mm(hh_mm)
        self._scheduler.add_job(
            job,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=self._tz),
            id="close-day",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        log.info("Scheduled day close: %02d:%02d (%s)", hour, minute, self._tz)
