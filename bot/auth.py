"""Validation of Telegram Mini App ``initData``.

When a Mini App is opened, Telegram hands the page a signed ``initData`` query
string. The backend must verify that signature before trusting the ``user.id``
inside it — otherwise anyone could POST fake results for any user.

Algorithm (per Telegram docs, "Validating data received via the Mini App"):

1. Split ``initData`` into key/value pairs; pull out ``hash``.
2. Build ``data_check_string`` = the remaining pairs as ``key=value`` lines,
   sorted by key, joined by ``\\n``.
3. ``secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)``.
4. Expected hash = ``HMAC_SHA256(key=secret_key, msg=data_check_string)`` hex.
5. Constant-time compare with the supplied ``hash``; optionally reject stale
   ``auth_date``.

This module is pure (no aiogram / aiohttp) and unit-tested with constructed
signatures.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

__all__ = ["InitData", "validate_init_data"]


@dataclass(frozen=True, slots=True)
class InitData:
    user_id: int
    username: str | None
    first_name: str | None
    auth_date: int


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age: int | None = None,
    *,
    now: float | None = None,
) -> InitData | None:
    """Return the authenticated :class:`InitData` or ``None`` if invalid.

    ``max_age`` (seconds) rejects signatures whose ``auth_date`` is older than
    that; ``None`` disables the freshness check. ``now`` is injectable for tests.
    """
    if not init_data or not bot_token:
        return None

    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    expected = hmac.new(
        _secret_key(bot_token), data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None

    try:
        auth_date = int(data.get("auth_date", "0"))
    except ValueError:
        return None

    if max_age is not None and auth_date > 0:
        current = time.time() if now is None else now
        if current - auth_date > max_age:
            return None

    user_raw = data.get("user")
    if not user_raw:
        return None
    try:
        user = json.loads(user_raw)
        user_id = int(user["id"])
    except (ValueError, KeyError, TypeError):
        return None

    return InitData(
        user_id=user_id,
        username=user.get("username"),
        first_name=user.get("first_name"),
        auth_date=auth_date,
    )
