"""Tests for the aiohttp result-collector (auth + language handling)."""

from __future__ import annotations

import pytest

from bot.config import load_config
from bot.db import VerbaDB
from bot.web import create_app
from tests.test_auth import BOT_TOKEN, make_init_data


def _config():
    return load_config(
        {
            "BOT_TOKEN": BOT_TOKEN,
            "WEBAPP_URL": "https://game.example",
            "INIT_DATA_MAX_AGE": "999999999999",  # effectively no expiry for tests
        }
    )


@pytest.fixture()
def db(tmp_path):
    return VerbaDB(tmp_path / "web.db")


async def test_result_recorded_with_valid_initdata(aiohttp_client, db):
    client = await aiohttp_client(create_app(db, _config()))
    init = make_init_data({"id": 555, "username": "bob"}, 1_700_000_000)
    resp = await client.post(
        "/api/result",
        json={"initData": init, "day": "1.05.2026", "lang": "ru", "status": "won", "attempts": 3},
    )
    assert resp.status == 200
    row = db.get_result(555, "1.05.2026", "ru")
    assert row is not None and row.status == "won" and row.attempts == 3


async def test_result_rejects_forged_initdata(aiohttp_client, db):
    client = await aiohttp_client(create_app(db, _config()))
    init = make_init_data({"id": 555}, 1_700_000_000).replace("555", "999")
    resp = await client.post(
        "/api/result",
        json={"initData": init, "day": "1.05.2026", "lang": "ru", "status": "won"},
    )
    assert resp.status == 401
    assert db.get_result(999, "1.05.2026", "ru") is None


async def test_result_rejects_bad_lang(aiohttp_client, db):
    client = await aiohttp_client(create_app(db, _config()))
    init = make_init_data({"id": 1}, 1_700_000_000)
    resp = await client.post(
        "/api/result",
        json={"initData": init, "day": "1.05.2026", "lang": "fr", "status": "won"},
    )
    assert resp.status == 400


async def test_started_marks_in_progress(aiohttp_client, db):
    client = await aiohttp_client(create_app(db, _config()))
    init = make_init_data({"id": 7}, 1_700_000_000)
    resp = await client.post(
        "/api/started", json={"initData": init, "day": "1.05.2026", "lang": "uk"}
    )
    assert resp.status == 200
    assert db.get_result(7, "1.05.2026", "uk").status == "in_progress"


async def test_healthz(aiohttp_client, db):
    client = await aiohttp_client(create_app(db, _config()))
    resp = await client.get("/healthz")
    assert resp.status == 200
