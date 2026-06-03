"""aiohttp result-collector for the Mini App.

The webapp (``webapp/tg-report.js``) POSTs game events here. Every write is
authenticated by validating the Telegram ``initData`` signature against the bot
token — the ``user.id`` inside a valid signature is the only identity we trust.

Endpoints:
    POST /api/started  {initData, day}                      -> mark in_progress
    POST /api/result   {initData, day, status, attempts, elapsed_ms} -> won/lost
    GET  /healthz                                            -> liveness probe

Runs in the same asyncio process as the bot (see ``main.py``), behind an HTTPS
reverse proxy in production.
"""

from __future__ import annotations

import logging

from aiohttp import web

from bot.auth import InitData, validate_init_data
from bot.config import Config
from bot.db import VerbaDB
from bot.i18n import t
from bot.stats import LANG_FLAGS, display_name

__all__ = ["create_app"]

log = logging.getLogger(__name__)

_VALID_RESULT_STATUS = {"won", "lost"}
_VALID_LANGS = {"ru", "uk", "en"}


@web.middleware
async def _cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        response = await handler(request)
    origin = request.app["allow_origin"]
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def _auth(request: web.Request, payload: dict):
    config: Config = request.app["config"]
    init_data = payload.get("initData", "")
    if not isinstance(init_data, str):
        return None
    return validate_init_data(init_data, config.bot_token, config.init_data_max_age)


async def _started(request: web.Request) -> web.Response:
    payload = await _json(request)
    auth = _auth(request, payload)
    if auth is None:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

    db: VerbaDB = request.app["db"]
    day = str(payload.get("day", ""))
    lang = str(payload.get("lang", ""))
    if not day:
        return web.json_response({"ok": False, "error": "missing day"}, status=400)
    if lang not in _VALID_LANGS:
        return web.json_response({"ok": False, "error": "bad lang"}, status=400)

    db.add_user(auth.user_id, auth.username, auth.first_name)
    db.start_result(auth.user_id, day, lang)
    return web.json_response({"ok": True})


async def _result(request: web.Request) -> web.Response:
    payload = await _json(request)
    auth = _auth(request, payload)
    if auth is None:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

    status = payload.get("status")
    if status not in _VALID_RESULT_STATUS:
        return web.json_response({"ok": False, "error": "bad status"}, status=400)

    day = str(payload.get("day", ""))
    lang = str(payload.get("lang", ""))
    if not day:
        return web.json_response({"ok": False, "error": "missing day"}, status=400)
    if lang not in _VALID_LANGS:
        return web.json_response({"ok": False, "error": "bad lang"}, status=400)

    attempts = _clamp_attempts(payload.get("attempts"))
    elapsed_ms = _opt_int(payload.get("elapsed_ms"))

    db: VerbaDB = request.app["db"]
    db.add_user(auth.user_id, auth.username, auth.first_name)
    newly = db.record_result(auth.user_id, day, lang, status, attempts, elapsed_ms)
    log.info(
        "Recorded %s for user %d on %s/%s (attempts=%s, newly=%s)",
        status,
        auth.user_id,
        day,
        lang,
        attempts,
        newly,
    )
    if newly:
        # Attribute the result to every group the player is registered in; the
        # returned chats are the ones where they were *first* to win this round.
        first_in = db.credit_competition(auth.user_id, day, lang, status)
        if status == "won" and first_in:
            await _announce_win(request.app, auth, lang, attempts, first_in)
    return web.json_response({"ok": True})


async def _announce_win(
    app: web.Application, auth: InitData, lang: str, attempts: int | None, chat_ids: list[int]
) -> None:
    """Announce a first win to the given groups (never revealing the word)."""
    bot = app.get("bot")
    db: VerbaDB = app["db"]
    if bot is None:
        return
    name = display_name(auth.first_name, auth.username, auth.user_id)
    flag = LANG_FLAGS.get(lang, "")
    for chat_id in chat_ids:
        chat_lang = db.get_chat_lang(chat_id)
        text = t("group_win", chat_lang, name=name, flag=flag, attempts=attempts or "?")
        try:
            await bot.send_message(chat_id, text)
        except Exception:  # noqa: BLE001 — a single failed group send must not 500 the API
            log.exception("Failed to announce win to chat %d", chat_id)


async def _healthz(_: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def _json(request: web.Request) -> dict:
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _opt_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _clamp_attempts(value: object) -> int | None:
    n = _opt_int(value)
    if n is None:
        return None
    return max(1, min(6, n))


def create_app(db: VerbaDB, config: Config, bot=None) -> web.Application:
    app = web.Application(middlewares=[_cors_middleware])
    app["db"] = db
    app["config"] = config
    app["bot"] = bot  # used to announce wins to groups; None disables announcements
    app["allow_origin"] = _origin(config.webapp_url)
    app.router.add_post("/api/started", _started)
    app.router.add_post("/api/result", _result)
    # CORS preflight (OPTIONS) is handled by _cors_middleware for every route.
    app.router.add_get("/healthz", _healthz)
    return app


def _origin(webapp_url: str) -> str:
    """Derive an allowed CORS origin from the configured webapp URL."""
    if not webapp_url:
        return "*"
    from urllib.parse import urlparse

    parsed = urlparse(webapp_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return "*"
