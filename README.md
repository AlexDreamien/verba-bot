# Verba Daily Bot

A Telegram bot around a daily 5-letter word-guessing game ("Wordle"-style) with
its **own engine** and word lists for **three languages — Russian, Ukrainian,
English**. The bot broadcasts the day's game to subscribers, opens it as a
**Telegram Mini App**, and collects each player's result — guessed / failed /
didn't finish, number of attempts, and solve time — into a shared daily summary
and per-player stats.

The game is original work — the engine and word lists are written from scratch
(inspired by classic daily word games like Wordle), so the whole repo is MIT.
See [`NOTICE.md`](NOTICE.md).

## The game

`webapp/` is a self-contained static Mini App:

- `engine.js` — the word engine: daily word picked deterministically by date,
  duplicate-letter coloring, an on-screen keyboard per locale, progress saved in
  `localStorage`, and an in-game **🇷🇺 / 🇺🇦 / 🇬🇧 language switch** (each locale
  has its own word list, keyboard layout, UI text, and word of the day).
- `words.js` — hand-curated 5-letter word lists per locale.
- It announces outcomes via a global `logEvent(name, {lang, day})` that the
  reporting layer (`tg-report.js`) listens to.

## How it works

```
  Telegram user
      │  /start, /play, /stats, /me           ┌──────────────────────────┐
      ▼                                        │  bot (aiogram, polling)   │
  ┌────────────┐   "Play" (WebApp button)      │  + scheduler (APScheduler)│
  │  Telegram  │◀──────────────────────────────│  + collector (aiohttp)    │
  │            │                               └────────────┬─────────────┘
  │  Mini App  │   POST /api/started (initData)              │ SQLite
  │  (webapp/) │──────────────────────────────────────────▶ │ users + results
  │            │   POST /api/result  (initData, attempts,    │
  └────────────┘                       elapsed, won/lost)    ▼
                                               aggregated daily & personal stats
```

1. A user runs `/start` and is subscribed. `/play` (or an admin `/broadcast`, or
   the daily schedule) sends a message with a **Play** button that opens the
   game as a Mini App inside Telegram.
2. `webapp/tg-report.js` reads Telegram's signed `initData`, records when the
   player started, and **wraps the engine's `logEvent`** to detect a win
   (`game_success`) or loss (`game_failed`). Each event carries `{lang, day}`,
   so a player can play all three languages in a day and each is tracked
   independently.
3. On start and on finish it POSTs to the bot's aiohttp collector. Every write
   is authenticated by validating the `initData` HMAC against the bot token, so
   the `user.id` cannot be spoofed.
4. At the configured end-of-day time the bot **closes the day**: players still
   `in_progress` become `unfinished`, subscribers who played no locale at all
   get a single `not_played` row, and a summary is posted.

Outcomes per (user, day, lang): `in_progress → won | lost | unfinished`, plus a
per-day `not_played` for subscribers who didn't play.

## Commands

| Command | Who | Effect |
|---|---|---|
| `/start` | everyone | subscribe + welcome |
| `/play` | everyone | get today's game button |
| `/stats` | everyone | today's summary in DM; the group leaderboard in a group |
| `/me` | everyone | personal history, win rate, streaks |
| `/register` | everyone | join the current group's competition (group only) |
| `/unregister` | everyone | leave the current group's competition (group only) |
| `/startseason` | group admins | begin a new season (resets the leaderboard) |
| `/finishseason` | group admins | close the season and post final standings |
| `/stop` | everyone | unsubscribe |
| `/lang` | everyone | switch language (user's in DM, the group's in a group) |
| `/menu`, `/help` | everyone | quick-action button menu |
| `/broadcast` | admins | send the game to all subscribers now |

Commands appear in Telegram's `/` hint menu (localized via `setMyCommands`), and
the bot replies with a button menu on `/menu`, `/help`, or when mentioned in a group.

## Groups & competitions

Anyone can play and keep **personal** stats (`/me`) without joining anything.
A group can also run a **competition**:

- Players opt in with **`/register`**, sent **inside that group**. Registration
  is **per group** — if you're in two groups, `/register` in each separately.
- `/stats` in a group shows the **leaderboard** of registered players: points,
  ✅ guessed, ❌ missed, 💤 skipped.
- A **round** is one `(day, language)` — three words a day, scored independently.
- **Scoring:** guessing the word = **+1**; being the **first** registered player
  in the group to guess that round's word = **+3** (instead of 1).
- When someone is **first** in a round, the bot announces it to that group —
  **without the word**, and only once per round per language (so up to three
  announcements a day). Later guessers that round get their point silently.
- At day close, any round a registered player didn't finish (unplayed or started
  but not solved) is counted as a **skip** for that group.
- **Seasons.** Each group runs in seasons (it starts in **season 1**). A group
  admin can **`/finishseason`** (posts the final standings) and then
  **`/startseason`** to begin the next one — which **resets** the visible
  leaderboard while history is preserved. The season number is shown in `/stats`.
  While no season is active (after a finish, before the next start) games are
  still recorded personally but earn no competition points.

A win flows from the Mini App (opened in DM — group `web_app` buttons aren't
allowed) and is credited to every group the player is registered in. A normal
bot can't enumerate group members, which is exactly why competitions are
opt-in via `/register` rather than automatic.

## Architecture

"Clean core + thin layer". The core is free of aiogram/aiohttp and unit-tested:

| Module | Responsibility |
|---|---|
| `bot/auth.py` | validate Telegram `initData` HMAC signature |
| `bot/db.py` | SQLite store (`users`, `results` keyed by user/day/lang); idempotent writes |
| `bot/stats.py` | aggregate daily + per-user stats (with per-language breakdown), format text |
| `bot/daily.py` | `day_key` matching the engine's `dayKey` format (Kyiv `d.mm.yyyy`) |
| `bot/i18n.py` | RU/EN bot-message catalog |
| `bot/config.py` | environment parsing |

Thin layer (not unit-tested): `bot/handlers/` (routers), `bot/web.py` (aiohttp
collector), `bot/scheduler.py` (APScheduler jobs), `bot/broadcast.py`,
`bot/keyboards.py`, `main.py` (wires polling + collector + scheduler in one
asyncio process).

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                              # fill BOT_TOKEN, ADMIN_IDS, WEBAPP_URL
pytest && ruff check . && black --check .
python main.py
```

Because a Mini App must be served over HTTPS and reachable by Telegram, local
development needs a tunnel:

```bash
# 1. serve the game
python -m http.server 8000 --directory webapp
# 2. expose the aiohttp collector (port 8080) over HTTPS
cloudflared tunnel --url http://localhost:8080      # or: ngrok http 8080
```

- Put the collector's HTTPS URL into `webapp/config.js` (`VERBA_BACKEND_URL`).
- Host `webapp/` over HTTPS too (a second tunnel, or GitHub Pages) and register
  that URL as the **Mini App URL** in [@BotFather] → *Bot Settings → Menu Button*
  (or via a Web App from a button).
- Set the same URL as `WEBAPP_URL` in `.env`.

[@BotFather]: https://t.me/BotFather

## Deploy (production)

**Mini App → GitHub Pages.** Push to `main`; `.github/workflows/pages.yml`
publishes `webapp/`. Enable Pages (Settings → Pages → *GitHub Actions*). The
resulting URL is your `WEBAPP_URL` and your @BotFather Mini App URL. Edit
`webapp/config.js` so `VERBA_BACKEND_URL` points at your collector's HTTPS host.

**Bot + collector → Fly.io (recommended).** Fly builds the `Dockerfile`, gives a
free HTTPS host at `https://<app>.fly.dev`, and provides a persistent volume for
SQLite. `fly.toml` keeps one machine always running (the bot polls continuously)
and health-checks `/healthz`.

```bash
flyctl auth signup                       # or: flyctl auth login
flyctl apps create verba-bot             # pick a globally-unique name
flyctl volumes create verba_data --region waw --size 1
flyctl secrets set BOT_TOKEN=... ADMIN_IDS=123,456
flyctl deploy
```

Then set `VERBA_BACKEND_URL = "https://<app>.fly.dev"` in `webapp/config.js`,
commit (Pages redeploys), and check `https://<app>.fly.dev/healthz`.

**Bot + collector → your own Docker host.** Alternatively run the container
behind a reverse proxy that terminates TLS (Caddy/nginx) → port `8080`:

```bash
cp .env.example .env        # set BOT_TOKEN, ADMIN_IDS, WEBAPP_URL
docker compose up -d --build
```

Example Caddy snippet:

```
verba-api.example.com {
    reverse_proxy localhost:8080
}
```

Then `VERBA_BACKEND_URL = "https://verba-api.example.com"` in `webapp/config.js`.

## Configuration

All via environment variables (see `.env.example`): `BOT_TOKEN`, `ADMIN_IDS`,
`WEBAPP_URL`, `DB_PATH`, `WEB_HOST`/`WEB_PORT`, `INIT_DATA_MAX_AGE`, `TZ`,
`BROADCAST_CRON` (empty to disable auto-broadcast), `CLOSE_DAY_AT`,
`SUMMARY_TO_SUBSCRIBERS`.

## Notes & limitations

- **Solve time is an approximation** — measured from when the player first opens
  that locale's puzzle that day (persisted in `localStorage`) to the win.
- The day key uses Kyiv time for the daily rollover; the engine and `bot/daily.py`
  produce the identical `d.mm.yyyy` string so `close_day` lines up with reports.
- Word lists are modest seed sets; the daily word is `date mod len(list)`, so a
  longer list just delays repeats. Extend them freely — `tests/test_words.py`
  validates length/charset/uniqueness.

## Out of scope (deliberate)

One daily puzzle per language (no retro/random modes), no leaderboard ranking
messages, no web dashboard, no per-user timezones, no payments.

## License

The entire repository is **MIT** licensed (see [`LICENSE`](LICENSE)). The game is
an original implementation (inspired by classic daily word games like Wordle); it
bundles no third-party code or word data. See [`NOTICE.md`](NOTICE.md).
