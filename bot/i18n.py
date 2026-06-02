"""Tiny message catalog for the bot (Russian + English).

Repo content is English, but user-facing bot text is localized. Each user has a
``lang`` column; handlers call :func:`t` with that language. The Verba game
itself stays Ukrainian — only the bot's own messages are translated here.

``t(key, lang, **kw)`` looks up the key for ``lang``, falls back to English, and
applies ``str.format(**kw)``. The test suite asserts both locales expose the
same keys.
"""

from __future__ import annotations

__all__ = ["DEFAULT_LANG", "LANGS", "t"]

DEFAULT_LANG = "ru"
LANGS = ("ru", "en")

MESSAGES: dict[str, dict[str, str]] = {
    "ru": {
        "welcome": (
            "Привет! Это бот ежедневной игры «Verba» — угадай слово из 5 букв за 6 попыток.\n\n"
            "Ты подписан на ежедневную рассылку. Команды:\n"
            "/play — получить ссылку на сегодняшнюю игру\n"
            "/stats — общая статистика за день\n"
            "/me — твоя личная статистика\n"
            "/stop — отписаться\n"
            "/lang — сменить язык"
        ),
        "already_subscribed": "Ты уже подписан. /play — сыграть в сегодняшнюю игру.",
        "unsubscribed": "Ты отписался от рассылки. /start — подписаться снова.",
        "not_subscribed": "Ты и так не подписан. /start — подписаться.",
        "play_prompt": "Сьогодні — гра «Verba». Натисни кнопку, щоб зіграти 👇",
        "play_button": "🎮 Грати",
        "no_webapp": "Адрес игры не настроен (WEBAPP_URL). Обратись к администратору.",
        "broadcast_not_admin": "Эта команда только для администраторов.",
        "broadcast_done": "Рассылка отправлена: {ok} из {total}.",
        "broadcast_no_subs": "Нет подписчиков для рассылки.",
        "stats_title": "📊 Статистика за {day}",
        "stats_none": "За {day} ещё нет данных.",
        "stats_body": (
            "Игроков: {total}\n"
            "✅ угадали: {won}\n"
            "❌ не угадали: {lost}\n"
            "⏳ не доиграли: {unfinished}\n"
            "💤 не играли: {not_played}\n"
            "{extra}"
        ),
        "stats_extra": "Среднее число попыток: {avg_attempts}\nСреднее время: {avg_time}",
        "me_title": "👤 Твоя статистика",
        "me_none": "Ты ещё не играл. /play — начать.",
        "me_body": (
            "Сыграно дней: {played}\n"
            "✅ побед: {wins}\n"
            "❌ поражений: {losses}\n"
            "Процент побед: {win_rate}%\n"
            "Лучший результат: {best}\n"
            "Текущая серия: {streak} 🔥\n"
            "Лучшая серия: {max_streak}"
        ),
        "best_none": "—",
        "best_attempts": "{n}/6",
        "lang_choose": "Выбери язык:",
        "lang_set": "Язык переключён на русский.",
        "summary_title": "🏁 Итоги дня {day}",
        "time_seconds": "{s} с",
        "time_minutes": "{m} мин {s} с",
    },
    "en": {
        "welcome": (
            "Hi! This is the daily «Verba» word-game bot — guess the 5-letter word in 6 tries.\n\n"
            "You're subscribed to the daily broadcast. Commands:\n"
            "/play — get today's game link\n"
            "/stats — global stats for the day\n"
            "/me — your personal stats\n"
            "/stop — unsubscribe\n"
            "/lang — change language"
        ),
        "already_subscribed": "You're already subscribed. /play to play today's game.",
        "unsubscribed": "You've unsubscribed. /start to subscribe again.",
        "not_subscribed": "You're not subscribed. /start to subscribe.",
        "play_prompt": "Today's «Verba» game is ready. Tap the button to play 👇",
        "play_button": "🎮 Play",
        "no_webapp": "The game URL is not configured (WEBAPP_URL). Contact the admin.",
        "broadcast_not_admin": "This command is for administrators only.",
        "broadcast_done": "Broadcast sent: {ok} of {total}.",
        "broadcast_no_subs": "No subscribers to broadcast to.",
        "stats_title": "📊 Stats for {day}",
        "stats_none": "No data for {day} yet.",
        "stats_body": (
            "Players: {total}\n"
            "✅ guessed: {won}\n"
            "❌ failed: {lost}\n"
            "⏳ unfinished: {unfinished}\n"
            "💤 didn't play: {not_played}\n"
            "{extra}"
        ),
        "stats_extra": "Average attempts: {avg_attempts}\nAverage time: {avg_time}",
        "me_title": "👤 Your stats",
        "me_none": "You haven't played yet. /play to start.",
        "me_body": (
            "Days played: {played}\n"
            "✅ wins: {wins}\n"
            "❌ losses: {losses}\n"
            "Win rate: {win_rate}%\n"
            "Best result: {best}\n"
            "Current streak: {streak} 🔥\n"
            "Best streak: {max_streak}"
        ),
        "best_none": "—",
        "best_attempts": "{n}/6",
        "lang_choose": "Choose a language:",
        "lang_set": "Language switched to English.",
        "summary_title": "🏁 Day {day} summary",
        "time_seconds": "{s}s",
        "time_minutes": "{m}m {s}s",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **kw: object) -> str:
    """Return the localized, formatted message for ``key`` in ``lang``."""
    catalog = MESSAGES.get(lang) or MESSAGES[DEFAULT_LANG]
    template = catalog.get(key) or MESSAGES[DEFAULT_LANG].get(key) or key
    try:
        return template.format(**kw)
    except (KeyError, IndexError):
        return template
