"""Tests for Telegram initData signature validation."""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import urlencode

from bot.auth import validate_init_data

BOT_TOKEN = "123456:TEST-TOKEN"


def make_init_data(user: dict, auth_date: int, token: str = BOT_TOKEN) -> str:
    """Build a correctly-signed initData string, like Telegram would."""
    data = {"user": json.dumps(user, separators=(",", ":")), "auth_date": str(auth_date)}
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def test_valid_signature_returns_user():
    init = make_init_data({"id": 42, "username": "alice", "first_name": "Alice"}, 1_700_000_000)
    result = validate_init_data(init, BOT_TOKEN, max_age=None)
    assert result is not None
    assert result.user_id == 42
    assert result.username == "alice"
    assert result.auth_date == 1_700_000_000


def test_tampered_payload_rejected():
    init = make_init_data({"id": 42}, 1_700_000_000)
    # Change the user id after signing: the hash no longer matches.
    tampered = init.replace("42", "99")
    assert tampered != init
    assert validate_init_data(tampered, BOT_TOKEN, max_age=None) is None


def test_wrong_token_rejected():
    init = make_init_data({"id": 42}, 1_700_000_000)
    assert validate_init_data(init, "999999:OTHER-TOKEN", max_age=None) is None


def test_expired_rejected_with_max_age():
    init = make_init_data({"id": 42}, 1_000)
    # now is far in the future relative to auth_date -> stale
    assert validate_init_data(init, BOT_TOKEN, max_age=3600, now=1_000_000) is None


def test_fresh_accepted_with_max_age():
    init = make_init_data({"id": 7}, 1_000_000)
    result = validate_init_data(init, BOT_TOKEN, max_age=3600, now=1_000_100)
    assert result is not None and result.user_id == 7


def test_missing_hash_rejected():
    assert validate_init_data("user=%7B%22id%22%3A1%7D&auth_date=1", BOT_TOKEN) is None


def test_empty_inputs_rejected():
    assert validate_init_data("", BOT_TOKEN) is None
    assert validate_init_data("anything", "") is None
