"""Tiny message catalog for the bot (Ukrainian + Russian + English).

Repo content is English, but user-facing bot text is localized. Each user has a
``lang`` column; handlers call :func:`t` with that language. The default language
is Ukrainian. The game (webapp) has its own independent ru/uk/en switch.

``t(key, lang, **kw)`` looks up the key for ``lang``, falls back to the default
language, and applies ``str.format(**kw)``. The test suite asserts every locale
exposes the same keys.
"""

from __future__ import annotations

__all__ = ["DEFAULT_LANG", "LANGS", "t"]

DEFAULT_LANG = "uk"
LANGS = ("uk", "ru", "en")

MESSAGES: dict[str, dict[str, str]] = {
    "uk": {
        "welcome": (
            "Привіт! Це бот щоденної гри «Verba» — вгадай слово з 5 літер за 6 спроб.\n\n"
            "Ти підписаний на щоденну розсилку. Команди:\n"
            "/play — отримати посилання на сьогоднішню гру\n"
            "/stats — статистика (у групі — заліковий рейтинг)\n"
            "/me — твоя особиста статистика\n"
            "/register — взяти участь у заліку групи (напиши в групі)\n"
            "/stop — відписатися\n"
            "/lang — змінити мову"
        ),
        "already_subscribed": "Ти вже підписаний. /play — зіграти в сьогоднішню гру.",
        "unsubscribed": "Ти відписався від розсилки. /start — підписатися знову.",
        "not_subscribed": "Ти і так не підписаний. /start — підписатися.",
        "play_prompt": "Сьогодні — гра «Verba». Натисни кнопку, щоб зіграти 👇",
        "play_in_private": "Гру можна відкрити лише в особистому чаті з ботом 👇",
        "play_button": "🎮 Грати",
        "no_webapp": "Адресу гри не налаштовано (WEBAPP_URL). Звернись до адміністратора.",
        "broadcast_not_admin": "Ця команда лише для адміністраторів.",
        "broadcast_done": "Розсилку надіслано: {ok} з {total}.",
        "broadcast_no_subs": "Немає підписників для розсилки.",
        "stats_title": "📊 Статистика за {day}",
        "stats_none": "За {day} ще немає даних.",
        "stats_body": (
            "Гравців: {total}\n"
            "✅ вгадали: {won}\n"
            "❌ не вгадали: {lost}\n"
            "⏳ не догравали: {unfinished}\n"
            "💤 не грали: {not_played}\n"
            "{extra}"
        ),
        "stats_extra": "Середня кількість спроб: {avg_attempts}\nСередній час: {avg_time}",
        "me_title": "👤 Твоя статистика",
        "me_none": "Ти ще не грав. /play — почати.",
        "me_body": (
            "Зіграно днів: {played}\n"
            "✅ перемог: {wins}\n"
            "❌ поразок: {losses}\n"
            "Відсоток перемог: {win_rate}%\n"
            "Найкращий результат: {best}\n"
            "Поточна серія: {streak} 🔥\n"
            "Найкраща серія: {max_streak}"
        ),
        "best_none": "—",
        "best_attempts": "{n}/6",
        "lang_choose": "Обери мову:",
        "lang_set": "Мову змінено на українську.",
        "lang_set_group": "Мову групи змінено на українську.",
        "menu_title": "Що зробити?",
        "btn_stats": "📊 Статистика",
        "btn_me": "👤 Я",
        "btn_lang": "🌐 Мова",
        "btn_help": "❓ Довідка",
        "comp_title": "🏆 Заліковий рейтинг групи · Сезон {season}",
        "comp_empty": "Поки ніхто не зареєструвався. Напишіть /register у групі, щоб брати участь у заліку.",
        "comp_row": "{rank} {name} — {score} 🏆 (✅{wins} ❌{losses} 💤{skips})",
        "comp_legend": (
            "🏆 очки · ✅ вгадано · ❌ не вгадано · 💤 пропущено\n"
            "Перше вгадане слово дня = 3 очки, інакше = 1."
        ),
        "register_done": "✅ {name}, тебе зараховано до заліку цієї групи! Тепер твої перемоги тут рахуються.",
        "register_already": "{name}, ти вже береш участь у заліку цієї групи.",
        "register_in_group": "Команда /register працює лише в груповому чаті. Додай мене в групу й напиши /register там.",
        "group_only": "Ця команда працює лише в груповому чаті.",
        "unregister_done": "👋 {name}, тебе виключено із заліку цієї групи. /register — повернутися.",
        "unregister_not": "{name}, ти не береш участі в заліку цієї групи.",
        "season_not_admin": "Керувати сезонами можуть лише адміністратори групи.",
        "season_started": "🏁 Сезон {n} стартував! Очки обнулено, залік починається з нуля.",
        "season_already": "⚠️ Сезон {n} уже триває. Спочатку заверши його: /finishseason.",
        "season_finished": "🏆 Сезон {n} завершено! Підсумки:",
        "season_none": "Зараз немає активного сезону. /startseason — почати новий.",
        "group_win": "🎉 {name} перш(ий/а) вгадав(-ла) слово дня {flag} за {attempts}/6! +3 очки 🏆 Саме слово — таємниця 🤫",
        "cmd_play": "Зіграти в сьогоднішню гру",
        "cmd_register": "Взяти участь у заліку групи",
        "cmd_unregister": "Вийти із заліку групи",
        "cmd_startseason": "Почати новий сезон (адмін)",
        "cmd_finishseason": "Завершити сезон (адмін)",
        "cmd_stats": "Статистика / рейтинг групи",
        "cmd_me": "Моя статистика",
        "cmd_lang": "Змінити мову",
        "cmd_help": "Команди та довідка",
        "cmd_stop": "Відписатися від розсилки",
        "summary_title": "🏁 Підсумки дня {day}",
        "time_seconds": "{s} с",
        "time_minutes": "{m} хв {s} с",
    },
    "ru": {
        "welcome": (
            "Привет! Это бот ежедневной игры «Verba» — угадай слово из 5 букв за 6 попыток.\n\n"
            "Ты подписан на ежедневную рассылку. Команды:\n"
            "/play — получить ссылку на сегодняшнюю игру\n"
            "/stats — статистика (в группе — зачёт)\n"
            "/me — твоя личная статистика\n"
            "/register — участвовать в зачёте группы (напиши в группе)\n"
            "/stop — отписаться\n"
            "/lang — сменить язык"
        ),
        "already_subscribed": "Ты уже подписан. /play — сыграть в сегодняшнюю игру.",
        "unsubscribed": "Ты отписался от рассылки. /start — подписаться снова.",
        "not_subscribed": "Ты и так не подписан. /start — подписаться.",
        "play_prompt": "Сегодня — игра «Verba». Нажми кнопку, чтобы сыграть 👇",
        "play_in_private": "Игру можно открыть только в личном чате с ботом 👇",
        "play_button": "🎮 Играть",
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
        "lang_set_group": "Язык группы переключён на русский.",
        "menu_title": "Что сделать?",
        "btn_stats": "📊 Статистика",
        "btn_me": "👤 Я",
        "btn_lang": "🌐 Язык",
        "btn_help": "❓ Помощь",
        "comp_title": "🏆 Зачёт группы · Сезон {season}",
        "comp_empty": "Пока никто не зарегистрировался. Напишите /register в группе, чтобы участвовать в зачёте.",
        "comp_row": "{rank} {name} — {score} 🏆 (✅{wins} ❌{losses} 💤{skips})",
        "comp_legend": (
            "🏆 очки · ✅ угадано · ❌ не угадано · 💤 пропущено\n"
            "Первое угаданное слово дня = 3 очка, остальные = 1."
        ),
        "register_done": "✅ {name}, ты в зачёте этой группы! Теперь твои победы здесь считаются.",
        "register_already": "{name}, ты уже участвуешь в зачёте этой группы.",
        "register_in_group": "Команда /register работает только в групповом чате. Добавь меня в группу и напиши /register там.",
        "group_only": "Эта команда работает только в групповом чате.",
        "unregister_done": "👋 {name}, ты вышел(а) из зачёта этой группы. /register — вернуться.",
        "unregister_not": "{name}, ты не участвуешь в зачёте этой группы.",
        "season_not_admin": "Управлять сезонами могут только администраторы группы.",
        "season_started": "🏁 Сезон {n} стартовал! Очки обнулены, зачёт начинается с нуля.",
        "season_already": "⚠️ Сезон {n} уже идёт. Сначала заверши его: /finishseason.",
        "season_finished": "🏆 Сезон {n} завершён! Итоги:",
        "season_none": "Сейчас нет активного сезона. /startseason — начать новый.",
        "group_win": "🎉 {name} первым(-ой) угадал(а) слово дня {flag} за {attempts}/6! +3 очка 🏆 Само слово — секрет 🤫",
        "cmd_play": "Сыграть в сегодняшнюю игру",
        "cmd_register": "Участвовать в зачёте группы",
        "cmd_unregister": "Выйти из зачёта группы",
        "cmd_startseason": "Начать новый сезон (админ)",
        "cmd_finishseason": "Завершить сезон (админ)",
        "cmd_stats": "Статистика / зачёт группы",
        "cmd_me": "Моя статистика",
        "cmd_lang": "Сменить язык",
        "cmd_help": "Команды и помощь",
        "cmd_stop": "Отписаться от рассылки",
        "summary_title": "🏁 Итоги дня {day}",
        "time_seconds": "{s} с",
        "time_minutes": "{m} мин {s} с",
    },
    "en": {
        "welcome": (
            "Hi! This is the daily «Verba» word-game bot — guess the 5-letter word in 6 tries.\n\n"
            "You're subscribed to the daily broadcast. Commands:\n"
            "/play — get today's game link\n"
            "/stats — stats (in a group: the leaderboard)\n"
            "/me — your personal stats\n"
            "/register — join a group's competition (send it in the group)\n"
            "/stop — unsubscribe\n"
            "/lang — change language"
        ),
        "already_subscribed": "You're already subscribed. /play to play today's game.",
        "unsubscribed": "You've unsubscribed. /start to subscribe again.",
        "not_subscribed": "You're not subscribed. /start to subscribe.",
        "play_prompt": "Today's «Verba» game is ready. Tap the button to play 👇",
        "play_in_private": "The game can only be opened in a private chat with the bot 👇",
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
        "lang_set_group": "Group language switched to English.",
        "menu_title": "What would you like?",
        "btn_stats": "📊 Stats",
        "btn_me": "👤 Me",
        "btn_lang": "🌐 Language",
        "btn_help": "❓ Help",
        "comp_title": "🏆 Group leaderboard · Season {season}",
        "comp_empty": "No one has registered yet. Send /register in the group to join the competition.",
        "comp_row": "{rank} {name} — {score} 🏆 (✅{wins} ❌{losses} 💤{skips})",
        "comp_legend": (
            "🏆 points · ✅ guessed · ❌ missed · 💤 skipped\n"
            "First to guess the day's word = 3 pts, otherwise = 1."
        ),
        "register_done": "✅ {name}, you're in this group's competition! Your wins here now count.",
        "register_already": "{name}, you're already in this group's competition.",
        "register_in_group": "/register only works in a group chat. Add me to a group and send /register there.",
        "group_only": "This command only works in a group chat.",
        "unregister_done": "👋 {name}, you've left this group's competition. /register to rejoin.",
        "unregister_not": "{name}, you're not in this group's competition.",
        "season_not_admin": "Only group admins can manage seasons.",
        "season_started": "🏁 Season {n} has started! Scores reset — the leaderboard begins fresh.",
        "season_already": "⚠️ Season {n} is already running. Finish it first: /finishseason.",
        "season_finished": "🏆 Season {n} finished! Final standings:",
        "season_none": "No season is active right now. /startseason to begin a new one.",
        "group_win": "🎉 {name} was first to guess today's word {flag} in {attempts}/6! +3 pts 🏆 The word stays secret 🤫",
        "cmd_play": "Play today's game",
        "cmd_register": "Join the group competition",
        "cmd_unregister": "Leave the group competition",
        "cmd_startseason": "Start a new season (admin)",
        "cmd_finishseason": "Finish the season (admin)",
        "cmd_stats": "Stats / group leaderboard",
        "cmd_me": "My stats",
        "cmd_lang": "Change language",
        "cmd_help": "Commands and help",
        "cmd_stop": "Unsubscribe",
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
