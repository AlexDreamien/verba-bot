"""Environment-backed configuration.

Pure parsing helpers (``parse_admin_ids``) are unit-tested; ``load_config``
just reads ``os.environ`` and wires them together.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from bot.daily import DEFAULT_TZ

__all__ = ["Config", "load_config", "parse_admin_ids"]


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    admin_ids: frozenset[int]
    webapp_url: str
    db_path: str
    web_host: str
    web_port: int
    init_data_max_age: int
    tz: str
    broadcast_cron: str | None
    close_day_at: str
    summary_to_subscribers: bool


def parse_admin_ids(raw: str | None) -> frozenset[int]:
    """Parse a comma-separated list of Telegram user IDs into a set of ints."""
    if not raw:
        return frozenset()
    ids: set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if chunk:
            ids.add(int(chunk))
    return frozenset(ids)


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Build a :class:`Config` from environment variables.

    Raises ``SystemExit`` if a required variable is missing.
    """
    env = os.environ if env is None else env

    token = env.get("BOT_TOKEN")
    if not token:
        raise SystemExit("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")

    broadcast_cron = env.get("BROADCAST_CRON", "").strip() or None

    return Config(
        bot_token=token,
        admin_ids=parse_admin_ids(env.get("ADMIN_IDS")),
        webapp_url=env.get("WEBAPP_URL", "").strip(),
        db_path=env.get("DB_PATH", "verba.db"),
        web_host=env.get("WEB_HOST", "0.0.0.0"),
        web_port=int(env.get("WEB_PORT", "8080")),
        init_data_max_age=int(env.get("INIT_DATA_MAX_AGE", "86400")),
        tz=env.get("TZ", DEFAULT_TZ),
        broadcast_cron=broadcast_cron,
        close_day_at=env.get("CLOSE_DAY_AT", "23:59").strip(),
        summary_to_subscribers=env.get("SUMMARY_TO_SUBSCRIBERS", "0").strip()
        in {"1", "true", "True"},
    )
