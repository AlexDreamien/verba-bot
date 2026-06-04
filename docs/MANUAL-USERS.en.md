# Verba — Player Guide

Verba is a daily word game (Wordle-style) inside Telegram. Every day there's a
new **5-letter** word and you get **6 tries**. Three languages are available:
**🇺🇦 Ukrainian, 🇷🇺 Russian, 🇬🇧 English** — each has its own dictionary and its own
word of the day. Bot: **@VerbaGame_bot**.

> The word changes once a day at **midnight Kyiv time**. Your progress for each
> day is saved — you can finish a started game later, but there's one word per day.

---

## Quick start

1. Open **@VerbaGame_bot** in Telegram and press **Start** (`/start`). You'll be
   subscribed to the daily nudge and see a menu of buttons.
2. Tap **🎮 Play** (or `/play`) — the game opens as a Telegram Mini App right
   inside the messenger.
3. Type 5-letter words and submit. The game ends for the day on a win or after 6
   failed tries.

## How to play

- Submit any valid 5-letter word. Tiles are colored:
  - 🟩 **green** — right letter, right spot;
  - 🟨 **yellow** — the letter is in the word, but elsewhere;
  - ⬛ **grey** — the letter isn't in the word.
- If a word **isn't in the dictionary**, the move is rejected and **no try is
  spent** — just type another.
- Repeated letters are colored correctly (like classic Wordle).
- The on-screen keyboard hints which letters you've found. You can also type on a
  physical keyboard.

### Switching language
The flags **🇺🇦 🇷🇺 🇬🇧** at the top switch language:
- **before your first guess** or **after** a game — free;
- **mid-game** — the current word counts as a **loss** (the bot asks to confirm).

### After a game
- **📤 Share** — builds your result as an emoji grid (🟩🟨⬛, **no letters** — no
  spoiler) and copies it so you can brag in a chat.
- **🔥 Streak** — how many days in a row you've solved it.
- **Countdown** — time left until the next word.
- **◐** (top) — **colorblind** palette (blue/orange instead of green/yellow).

---

## Personal stats

These work **in the bot's direct chat**:

| Command | What it does |
|---|---|
| `/play` | get today's game |
| `/me` | your stats: played, wins, win %, best result, streak |
| `/stats` | overall stats for the day (how many people solved it, etc.) |
| `/lang` | change the bot's interface language |
| `/stop` | unsubscribe from the daily nudge (`/start` to resubscribe) |
| `/menu`, `/help` | the button menu |

> You can play and keep personal stats **without registering** for anything.

---

## Playing in groups (the competition)

If the bot is in a group chat, that chat can run a shared **competition**. Your
personal stats stay separate — only people who **register** take part.

> To keep the chat clean, the bot replies to your actions (game, personal stats,
> language, menu and any buttons) **in your DM**, not in the group. Only
> registration, the leaderboard and win announcements stay in the chat. So open
> the bot in private first (`/start`). A non-admin can pull the leaderboard
> **once per hour** (admins anytime).

### How to join
- Send **`/register`** in the group, **or**
- tap the **Play** button in the group — it opens the bot's direct chat and
  **auto-registers** you in that group's competition.

Registration is **per group**: if you're in two groups with the bot, `/register`
in each. Leave with **`/unregister`** (your points are kept and come back if you
rejoin).

> Always open the game itself in the bot's **direct chat** — group chats can't
> host the game button, so Play sends you to the private chat.

### How points work
- A **round** is one word, one language, one day. There are 3 rounds a day
  (ru/uk/en); points per language are counted independently.
- For **guessing the word**: the fewer tries, the more points — `7 − tries`
  (1 try = **6**, 6 tries = **1**).
- For being **first in the group** to guess that round's word: **+3** on top.
- The table shows: 🏆 points · ✅ guessed · ❌ missed · 💤 skipped · ⌀ average
  tries. On a points tie, fewer average tries ranks higher.

### Announcements and skips
- When someone is **first** in the group to solve a round, the bot posts it to the
  chat — **without the word**. This happens at most 3 times a day (once per
  language).
- A **skip (💤)** is only counted for languages you've already played at least
  once that season. If you play only one language, you're not punished for the
  others.

### Table and seasons
- **`/stats`** in a group shows the current standings and the **season number**.
- Group admins switch seasons. Starting a new season **resets** the visible table
  (history is kept).
- **`/seasons`** — the group's past-season champions.

---

## Command cheat sheet

| Command | Where | What it does |
|---|---|---|
| `/start` | DM | subscribe + menu |
| `/play` | anywhere | today's game |
| `/me` | anywhere | personal stats |
| `/stats` | DM / group | day summary / competition table |
| `/register` | group | join the group's competition |
| `/unregister` | group | leave the group's competition |
| `/seasons` | group | past-season champions |
| `/lang` | anywhere | change language |
| `/stop` | DM | unsubscribe from the nudge |
| `/menu`, `/help` | anywhere | the button menu |

Have fun! 🎯
