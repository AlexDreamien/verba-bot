/*
 * A small, original 5-letter word-guessing engine (Wordle-style), built for
 * this project so the repository carries no third-party game code. Vanilla JS,
 * no framework.
 *
 * Features:
 *   - three locales (ru / uk / en), each with its own alphabet, on-screen
 *     keyboard layout, UI strings, and daily word; an in-game language switch;
 *   - deterministic daily word (date in Kyiv time modulo the locale word list);
 *   - standard two-pass coloring that handles duplicate letters correctly;
 *   - per-(locale, day) progress saved in localStorage;
 *   - it announces outcomes through the global `logEvent(name, details)` so the
 *     Telegram reporting layer (tg-report.js) can observe them without coupling:
 *       logEvent('game_started', {lang, day})
 *       logEvent('game_success', {index, lang, day})   // index = 0-based guess
 *       logEvent('game_failed',  {lang, day})
 */
(function () {
  "use strict";

  if (typeof window.logEvent !== "function") {
    window.logEvent = function () {}; // default no-op; tg-report.js wraps it
  }

  var WORD_LEN = 5;
  var MAX_GUESSES = 6;
  var EPOCH_UTC = Date.UTC(2022, 0, 1); // day 0 for the daily-word sequence
  var DAY_MS = 86400000;

  var LOCALES = {
    ru: {
      name: "Русский",
      flag: "🇷🇺",
      alphabet: "абвгдежзийклмнопрстуфхцчшщъыьэюя",
      rows: ["йцукенгшщзхъ", "фывапролджэ", "ячсмитьбю"],
      ui: {
        title: "Слово дня",
        prompt: "Угадай слово из 5 букв за 6 попыток",
        tooShort: "Слишком короткое слово",
        win: "Победа! 🎉",
        lose: "Не угадали. Слово: {w}",
        already: "Сегодня уже сыграно",
        notInList: "Нет такого слова в словаре",
        switchWarn: "Сменить язык? Текущее слово будет засчитано как проигрыш.",
        share: "📤 Поделиться",
        shareCopied: "Результат скопирован!",
        nextWord: "Следующее слово через {t}",
        streak: "Серия: {n} 🔥",
        cbHint: "Режим для дальтоников",
      },
    },
    uk: {
      name: "Українська",
      flag: "🇺🇦",
      alphabet: "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя",
      rows: ["йцукенгшщзхї", "фівапролджєґ", "ячсмитьбю"],
      ui: {
        title: "Слово дня",
        prompt: "Вгадай слово з 5 літер за 6 спроб",
        tooShort: "Замало літер",
        win: "Перемога! 🎉",
        lose: "Не вгадано. Слово: {w}",
        already: "Сьогодні вже зіграно",
        notInList: "Немає такого слова у словнику",
        switchWarn: "Змінити мову? Поточне слово буде зараховане як програш.",
        share: "📤 Поділитися",
        shareCopied: "Результат скопійовано!",
        nextWord: "Наступне слово через {t}",
        streak: "Серія: {n} 🔥",
        cbHint: "Режим для дальтоніків",
      },
    },
    en: {
      name: "English",
      flag: "🇬🇧",
      alphabet: "abcdefghijklmnopqrstuvwxyz",
      rows: ["qwertyuiop", "asdfghjkl", "zxcvbnm"],
      ui: {
        title: "Word of the day",
        prompt: "Guess the 5-letter word in 6 tries",
        tooShort: "Not enough letters",
        win: "You won! 🎉",
        lose: "Out of tries. The word was: {w}",
        already: "Already played today",
        notInList: "Not in word list",
        switchWarn: "Switch language? The current word will count as a loss.",
        share: "📤 Share",
        shareCopied: "Result copied!",
        nextWord: "Next word in {t}",
        streak: "Streak: {n} 🔥",
        cbHint: "Colorblind mode",
      },
    },
  };

  var ENTER = "↵";
  var BACK = "⌫";

  // --- date / daily word ---------------------------------------------------

  function kyivYMD() {
    // en-CA renders as YYYY-MM-DD.
    var iso = new Date().toLocaleDateString("en-CA", { timeZone: "Europe/Kyiv" });
    var p = iso.split("-");
    return { y: parseInt(p[0], 10), m: parseInt(p[1], 10), d: parseInt(p[2], 10) };
  }

  function dayKey(ymd) {
    // Must match bot/daily.py:day_key — "d.mm.yyyy", day not zero-padded.
    return ymd.d + "." + ("0" + ymd.m).slice(-2) + "." + ymd.y;
  }

  function dayNumber(ymd) {
    return Math.floor((Date.UTC(ymd.y, ymd.m - 1, ymd.d) - EPOCH_UTC) / DAY_MS);
  }

  // The answer pools are stored alphabetically; walking them by day number would
  // make tomorrow's word trivially predictable ("the next one alphabetically").
  // We deterministically permute each pool with a per-locale seed so the order is
  // scrambled but stable. (The word still lives client-side — this only removes
  // the casual tell, like the original Wordle.)
  var SHUFFLE_SEED = 0x9e3779b1;

  function mulberry32(a) {
    return function () {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function seedFor(lang) {
    var s = SHUFFLE_SEED;
    for (var i = 0; i < lang.length; i++) s = (Math.imul(s, 31) + lang.charCodeAt(i)) | 0;
    return s;
  }

  function seededOrder(len, seed) {
    var idx = [];
    for (var i = 0; i < len; i++) idx.push(i);
    var rnd = mulberry32(seed);
    for (var j = len - 1; j > 0; j--) {
      var k = Math.floor(rnd() * (j + 1));
      var tmp = idx[j];
      idx[j] = idx[k];
      idx[k] = tmp;
    }
    return idx;
  }

  function wordForToday(lang, ymd) {
    var pool = (window.VERBA_WORDS && window.VERBA_WORDS[lang]) || {};
    var list = pool.answers || [];
    if (!list.length) return "";
    var order = seededOrder(list.length, seedFor(lang));
    var n = dayNumber(ymd);
    var i = ((n % list.length) + list.length) % list.length;
    return list[order[i]];
  }

  // --- guess evaluation (two-pass, duplicate-safe) -------------------------

  function evaluate(guess, answer) {
    var result = new Array(WORD_LEN).fill("absent");
    var counts = {};
    var i, c;
    for (i = 0; i < WORD_LEN; i++) {
      c = answer[i];
      counts[c] = (counts[c] || 0) + 1;
    }
    for (i = 0; i < WORD_LEN; i++) {
      if (guess[i] === answer[i]) {
        result[i] = "correct";
        counts[guess[i]]--;
      }
    }
    for (i = 0; i < WORD_LEN; i++) {
      if (result[i] === "correct") continue;
      c = guess[i];
      if (counts[c] > 0) {
        result[i] = "present";
        counts[c]--;
      }
    }
    return result;
  }

  // --- state ---------------------------------------------------------------

  var state = null;

  function storageKey(lang, day) {
    return "verba:" + lang + ":" + day;
  }

  function loadProgress(lang, day) {
    try {
      var raw = localStorage.getItem(storageKey(lang, day));
      if (raw) return JSON.parse(raw);
    } catch (e) {
      /* ignore */
    }
    return { guesses: [], done: false, won: false };
  }

  function saveProgress() {
    try {
      localStorage.setItem(
        storageKey(state.lang, state.day),
        JSON.stringify({ guesses: state.guesses, done: state.done, won: state.won })
      );
    } catch (e) {
      /* ignore */
    }
  }

  function currentLang() {
    var saved = "";
    try {
      saved = localStorage.getItem("verba_lang") || "";
    } catch (e) {
      /* ignore */
    }
    if (LOCALES[saved]) return saved;
    var tg = window.Telegram && window.Telegram.WebApp;
    var code = tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.language_code;
    if (LOCALES[code]) return code;
    return "uk"; // default language
  }

  function init(lang) {
    var ymd = kyivYMD();
    var day = dayKey(ymd);
    var saved = loadProgress(lang, day);
    state = {
      lang: lang,
      ymd: ymd,
      day: day,
      answer: wordForToday(lang, ymd),
      guesses: saved.guesses || [],
      done: saved.done || false,
      won: saved.won || false,
      current: "",
      started: saved.guesses && saved.guesses.length > 0,
      accepted: new Set(((window.VERBA_WORDS[lang] || {}).accepted) || []),
    };
    render();
    if (state.done) {
      message(state.won ? ui().win : fmt(ui().lose, { w: state.answer.toUpperCase() }));
    }
  }

  function ui() {
    return LOCALES[state.lang].ui;
  }

  function fmt(tpl, vars) {
    return tpl.replace(/\{(\w+)\}/g, function (_, k) {
      return vars[k] != null ? vars[k] : "";
    });
  }

  // --- input ---------------------------------------------------------------

  function onChar(ch) {
    if (state.done) return;
    if (state.current.length >= WORD_LEN) return;
    if (LOCALES[state.lang].alphabet.indexOf(ch) === -1) return;
    if (!state.started) {
      state.started = true;
      window.logEvent("game_started", { lang: state.lang, day: state.day });
    }
    state.current += ch;
    render();
  }

  function onBackspace() {
    if (state.done) return;
    state.current = state.current.slice(0, -1);
    render();
  }

  function onEnter() {
    if (state.done) return;
    if (state.current.length < WORD_LEN) {
      message(ui().tooShort);
      haptic("error");
      return;
    }
    var guess = state.current;
    // Reject words that are not in the accepted dictionary: no attempt is spent
    // and no tiles are revealed.
    if (!state.accepted.has(guess)) {
      message(ui().notInList);
      haptic("error");
      return;
    }
    state.guesses.push(guess);
    state.current = "";

    if (guess === state.answer) {
      state.done = true;
      state.won = true;
      saveProgress();
      render();
      message(ui().win);
      haptic("success");
      window.logEvent("game_success", {
        index: state.guesses.length - 1,
        lang: state.lang,
        day: state.day,
      });
      return;
    }

    if (state.guesses.length >= MAX_GUESSES) {
      state.done = true;
      state.won = false;
      saveProgress();
      render();
      message(fmt(ui().lose, { w: state.answer.toUpperCase() }));
      haptic("error");
      window.logEvent("game_failed", { lang: state.lang, day: state.day });
      return;
    }

    saveProgress();
    render();
  }

  function commitLang(lang) {
    try {
      localStorage.setItem("verba_lang", lang);
    } catch (e) {
      /* ignore */
    }
    init(lang);
  }

  function abandonAsLoss() {
    // Switching away mid-game forfeits the current word: count it as a loss
    // and report it, so the daily stats stay consistent.
    state.done = true;
    state.won = false;
    saveProgress();
    window.logEvent("game_failed", { lang: state.lang, day: state.day });
  }

  function switchLang(lang) {
    if (!LOCALES[lang] || lang === state.lang) return;
    // Only an unfinished game with at least one submitted guess is forfeited.
    // Just typing letters (no guess yet), or an already-finished game, switches
    // freely without a loss.
    var inProgress = state.guesses.length > 0 && !state.done;
    if (!inProgress) {
      commitLang(lang);
      return;
    }
    var warn = ui().switchWarn;
    var proceed = function () {
      abandonAsLoss();
      commitLang(lang);
    };
    var tg = window.Telegram && window.Telegram.WebApp;
    // Use Telegram's native confirm only inside a real Telegram session
    // (initData present); in a plain browser its callback never fires.
    if (tg && tg.initData && typeof tg.showConfirm === "function") {
      tg.showConfirm(warn, function (ok) {
        if (ok) proceed();
      });
      return;
    }
    if (window.confirm(warn)) proceed();
  }

  // --- rendering -----------------------------------------------------------

  var els = {};

  function buildShell() {
    var root = document.getElementById("app");
    root.innerHTML = "";

    var header = div("header");
    els.title = div("title");
    header.appendChild(els.title);
    els.langbar = div("langbar");
    header.appendChild(els.langbar);
    els.cbtoggle = document.createElement("button");
    els.cbtoggle.className = "cbtoggle";
    els.cbtoggle.textContent = "◐";
    els.cbtoggle.onclick = toggleColorblind;
    header.appendChild(els.cbtoggle);
    root.appendChild(header);

    els.prompt = div("prompt");
    root.appendChild(els.prompt);

    els.board = div("board");
    root.appendChild(els.board);

    els.message = div("message");
    root.appendChild(els.message);

    els.actions = div("actions");
    root.appendChild(els.actions);

    els.keyboard = div("keyboard");
    root.appendChild(els.keyboard);

    applyColorblind(loadColorblind());
  }

  // --- colorblind palette --------------------------------------------------

  function loadColorblind() {
    try {
      return localStorage.getItem("verba_cb") === "1";
    } catch (e) {
      return false;
    }
  }

  function applyColorblind(on) {
    document.body.classList.toggle("cb", !!on);
    if (els.cbtoggle) els.cbtoggle.classList.toggle("active", !!on);
  }

  function toggleColorblind() {
    var on = !document.body.classList.contains("cb");
    applyColorblind(on);
    try {
      localStorage.setItem("verba_cb", on ? "1" : "0");
    } catch (e) {
      /* ignore */
    }
  }

  function renderLangbar() {
    els.langbar.innerHTML = "";
    Object.keys(LOCALES).forEach(function (lang) {
      var b = document.createElement("button");
      b.className = "langbtn" + (lang === state.lang ? " active" : "");
      b.textContent = LOCALES[lang].flag;
      b.title = LOCALES[lang].name;
      b.onclick = function () {
        switchLang(lang);
      };
      els.langbar.appendChild(b);
    });
  }

  function renderBoard() {
    els.board.innerHTML = "";
    var keyColors = {};
    for (var row = 0; row < MAX_GUESSES; row++) {
      var rowEl = div("row");
      var guess = state.guesses[row];
      var typing = row === state.guesses.length ? state.current : null;
      for (var col = 0; col < WORD_LEN; col++) {
        var cell = div("cell");
        if (guess != null) {
          var evald = evaluate(guess, state.answer);
          cell.textContent = guess[col].toUpperCase();
          cell.classList.add(evald[col]);
          // track best key color
          rankKey(keyColors, guess[col], evald[col]);
        } else if (typing != null && col < typing.length) {
          cell.textContent = typing[col].toUpperCase();
          cell.classList.add("filled");
        }
        rowEl.appendChild(cell);
      }
      els.board.appendChild(rowEl);
    }
    els._keyColors = keyColors;
  }

  function rankKey(map, ch, color) {
    var rank = { absent: 1, present: 2, correct: 3 };
    if (!map[ch] || rank[color] > rank[map[ch]]) map[ch] = color;
  }

  function renderKeyboard() {
    els.keyboard.innerHTML = "";
    var rows = LOCALES[state.lang].rows;
    var colors = els._keyColors || {};
    rows.forEach(function (rowStr, idx) {
      var rowEl = div("krow");
      if (idx === rows.length - 1) {
        rowEl.appendChild(keyButton(BACK, "wide", onBackspace));
      }
      rowStr.split("").forEach(function (ch) {
        var b = keyButton(ch.toUpperCase(), colors[ch] || "", function () {
          onChar(ch);
        });
        rowEl.appendChild(b);
      });
      if (idx === rows.length - 1) {
        rowEl.appendChild(keyButton(ENTER, "wide", onEnter));
      }
      els.keyboard.appendChild(rowEl);
    });
  }

  function keyButton(label, cls, handler) {
    var b = document.createElement("button");
    b.className = "key " + cls;
    b.textContent = label;
    b.onclick = handler;
    return b;
  }

  // --- end-of-game actions: share, streak, countdown ----------------------

  function renderActions() {
    var box = els.actions;
    box.innerHTML = "";
    stopCountdown();
    if (!state.done) return;

    var streak = localStreak(state.lang);
    if (streak > 0) {
      var st = div("streak");
      st.textContent = fmt(ui().streak, { n: streak });
      box.appendChild(st);
    }

    var btn = document.createElement("button");
    btn.className = "share";
    btn.textContent = ui().share;
    btn.onclick = doShare;
    box.appendChild(btn);

    els.countdown = div("countdown");
    box.appendChild(els.countdown);
    startCountdown();
  }

  function shareText() {
    var head =
      "Verba " +
      state.day +
      " " +
      LOCALES[state.lang].flag +
      " " +
      (state.won ? state.guesses.length : "X") +
      "/" +
      MAX_GUESSES;
    var grid = state.guesses
      .map(function (g) {
        return evaluate(g, state.answer)
          .map(function (c) {
            return c === "correct" ? "🟩" : c === "present" ? "🟨" : "⬛";
          })
          .join("");
      })
      .join("\n");
    return head + "\n" + grid;
  }

  function doShare() {
    var text = shareText();
    var tg = window.Telegram && window.Telegram.WebApp;
    if (window.VERBA_INLINE_SHARE && tg && typeof tg.switchInlineQuery === "function") {
      try {
        tg.switchInlineQuery(text, ["users", "groups", "channels"]);
        return;
      } catch (e) {
        /* fall through to clipboard */
      }
    }
    var ok = function () {
      message(ui().shareCopied);
      haptic("success");
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(ok, function () {
        message(text);
      });
    } else {
      message(text);
    }
  }

  function pad2(n) {
    return ("0" + n).slice(-2);
  }

  function secondsToKyivMidnight() {
    var now = new Date();
    var k = new Date(now.toLocaleString("en-US", { timeZone: "Europe/Kyiv" }));
    var secs = k.getHours() * 3600 + k.getMinutes() * 60 + k.getSeconds();
    return Math.max(0, 24 * 3600 - secs);
  }

  function updateCountdown() {
    if (!els.countdown) return;
    var s = secondsToKyivMidnight();
    var hhmmss = pad2(Math.floor(s / 3600)) + ":" + pad2(Math.floor((s % 3600) / 60)) + ":" + pad2(s % 60);
    els.countdown.textContent = fmt(ui().nextWord, { t: hhmmss });
  }

  function startCountdown() {
    updateCountdown();
    els._cd = window.setInterval(updateCountdown, 1000);
  }

  function stopCountdown() {
    if (els._cd) {
      window.clearInterval(els._cd);
      els._cd = null;
    }
  }

  function haptic(kind) {
    var tg = window.Telegram && window.Telegram.WebApp;
    var hf = tg && tg.HapticFeedback;
    if (!hf) return;
    try {
      if (kind === "success") hf.notificationOccurred("success");
      else if (kind === "error") hf.notificationOccurred("error");
      else hf.impactOccurred("light");
    } catch (e) {
      /* ignore */
    }
  }

  // Best-effort local streak from saved per-day progress (single device).
  function loadByDate(lang, ms) {
    var d = new Date(ms);
    var key =
      "verba:" +
      lang +
      ":" +
      (d.getUTCDate() + "." + pad2(d.getUTCMonth() + 1) + "." + d.getUTCFullYear());
    try {
      var raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function localStreak(lang) {
    var ymd = kyivYMD();
    var ms = Date.UTC(ymd.y, ymd.m - 1, ymd.d);
    var today = loadByDate(lang, ms);
    if (!today || !today.done) ms -= DAY_MS; // today unfinished -> count up to yesterday
    var streak = 0;
    for (var i = 0; i < 4000; i++) {
      var p = loadByDate(lang, ms);
      if (p && p.done && p.won) {
        streak++;
        ms -= DAY_MS;
      } else {
        break;
      }
    }
    return streak;
  }

  function render() {
    if (!els.board) buildShell();
    els.title.textContent = ui().title;
    els.prompt.textContent = ui().prompt;
    els.cbtoggle.title = ui().cbHint;
    renderLangbar();
    renderBoard();
    renderKeyboard();
    renderActions();
  }

  function message(text) {
    els.message.textContent = text;
  }

  function div(cls) {
    var d = document.createElement("div");
    d.className = cls;
    return d;
  }

  // --- physical keyboard ---------------------------------------------------

  window.addEventListener("keydown", function (e) {
    if (!state) return;
    if (e.key === "Enter") {
      onEnter();
    } else if (e.key === "Backspace") {
      onBackspace();
    } else if (e.key.length === 1) {
      onChar(e.key.toLowerCase());
    }
  });

  // --- boot ----------------------------------------------------------------

  function boot() {
    var tg = window.Telegram && window.Telegram.WebApp;
    if (tg) {
      try {
        tg.ready();
        tg.expand();
      } catch (e) {
        /* non-fatal */
      }
    }
    init(currentLang());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
