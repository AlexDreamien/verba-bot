# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

Telegram bot for a daily 5-letter word game (own engine, languages ru/uk/en). It
broadcasts the day's game as a **Telegram Mini App**, collects results (won /
lost / unfinished / not_played, attempts, solve time) via an HTTPS endpoint, and
reports daily + per-user stats. aiogram 3 (polling) + aiohttp (collector) +
APScheduler 3 + SQLite. See `README.md`.

## Build & test

```bash
pip install -r requirements-dev.txt
cp .env.example .env            # set BOT_TOKEN, ADMIN_IDS, WEBAPP_URL
python main.py
pytest                          # 86 tests
ruff check . && black --check .
```

## Architecture invariant

"Clean core + thin layer", same as the sibling `telegram-reminder-bot`.

- **Core (aiogram/aiohttp-free, unit-tested):** `bot/auth.py` (initData HMAC),
  `bot/db.py` (SQLite), `bot/stats.py` (aggregation + formatting), `bot/daily.py`
  (`day_key`), `bot/i18n.py`, `bot/config.py`. Keep new logic here.
- **Thin layer (not unit-tested):** `bot/handlers/` routers, `bot/web.py`,
  `bot/scheduler.py`, `bot/broadcast.py`, `bot/keyboards.py`, `main.py`. These
  only translate between Telegram/HTTP and the core — no business rules.

The Mini App (`webapp/`) is **all original**: `engine.js` (the word engine, with
the ru/uk/en language switch), `words.js` (curated word lists), `styles.css`,
`index.html`, `config.js`, `tg-report.js` (reporting). `main.py` runs polling +
the aiohttp collector + the scheduler in one asyncio process.

## Gotchas — do not regress

- **Every `/api/*` write authenticates `initData` before trusting `user.id`**
  (`bot/auth.validate_init_data`, HMAC over the bot token). Never read a user id
  straight from the request body — that's the whole point of the signature.
- **`results` is keyed by `(user_id, day, lang)`** so a player can play all three
  locales the same day independently. `not_played` (set at day close) is a single
  per-user row with the sentinel `lang = ''`, meaning "played no locale at all".
- **`record_result` is idempotent and never overwrites a terminal result.** The
  Mini App may retry; the SQL `UPDATE ... WHERE status NOT IN ('won','lost')`
  guards this. `start_result` likewise must not clobber a finished day.
- **`bot/daily.py:day_key` must match the engine's `dayKey` exactly:** `"d.mm.yyyy"`
  in Kyiv time — day NOT zero-padded, month zero-padded. The Mini App reports
  under that key and `close_day` must produce the identical string, or unfinished
  rows won't line up. Regression test in `test_daily.py`.
- **`tg-report.js` wraps the global `logEvent` and must load AFTER `engine.js`.**
  The engine emits `logEvent('game_started'|'game_success'|'game_failed', {lang,
  day})`; the reporting layer turns those into `/api/started` and `/api/result`.
  Keep that contract if you change either file.
- **Reporting is disabled without both a backend URL and a Telegram `initData`,**
  so the game still works as a plain webapp in a normal browser.
- **`close_day` / the broadcast run in the configured `TZ`** (Kyiv by default),
  while datetimes are computed from `datetime.now(UTC)` then converted.
- **Callback/message handlers guard `from_user is None`** before using `.id`.
- **`web_app` inline buttons are private-chat only.** In groups `/play` sends a
  URL button to the bot's DM instead (`play_link_keyboard`); never send a
  `web_app` button to a group (Telegram 400s and the message silently fails).
- **Group membership is best-effort.** `MembershipMiddleware` records senders the
  bot sees in groups; a normal bot can't enumerate members (full coverage needs
  group privacy disabled). Group stats / win announcements use this table.
- **Win announcements fire once.** `db.record_result` returns `True` only when it
  newly finalizes a game; `web._announce_win` keys off that so a retried POST
  doesn't re-announce. The announcement never includes the word.
- **`game.router` is included LAST** because its catch-all `F.text` handler
  (mentions → menu) would otherwise shadow command handlers in other routers.
  Menu callbacks use `query.from_user` (the requester), not the message author
  (the bot).

## Out of scope (deliberate)

One daily puzzle per language (no retro/random modes), no leaderboard ranking, no
web dashboard, no per-user timezones, no payments.

## License / credits

Entire repo is MIT. The game is original work (inspired by classic daily word
games like Wordle), bundling no third-party code or data — see `NOTICE.md`.
