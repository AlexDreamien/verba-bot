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

  function wordForToday(lang, ymd) {
    var list = (window.VERBA_WORDS && window.VERBA_WORDS[lang]) || [];
    if (!list.length) return "";
    var n = dayNumber(ymd);
    return list[((n % list.length) + list.length) % list.length];
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
    return "ru";
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
      return;
    }
    var guess = state.current;
    state.guesses.push(guess);
    state.current = "";

    if (guess === state.answer) {
      state.done = true;
      state.won = true;
      saveProgress();
      render();
      message(ui().win);
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
      window.logEvent("game_failed", { lang: state.lang, day: state.day });
      return;
    }

    saveProgress();
    render();
  }

  function switchLang(lang) {
    if (!LOCALES[lang] || lang === state.lang) return;
    try {
      localStorage.setItem("verba_lang", lang);
    } catch (e) {
      /* ignore */
    }
    init(lang);
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
    root.appendChild(header);

    els.prompt = div("prompt");
    root.appendChild(els.prompt);

    els.board = div("board");
    root.appendChild(els.board);

    els.message = div("message");
    root.appendChild(els.message);

    els.keyboard = div("keyboard");
    root.appendChild(els.keyboard);
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
        rowEl.appendChild(keyButton(ENTER, "wide", onEnter));
      }
      rowStr.split("").forEach(function (ch) {
        var b = keyButton(ch.toUpperCase(), colors[ch] || "", function () {
          onChar(ch);
        });
        rowEl.appendChild(b);
      });
      if (idx === rows.length - 1) {
        rowEl.appendChild(keyButton(BACK, "wide", onBackspace));
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

  function render() {
    if (!els.board) buildShell();
    els.title.textContent = ui().title;
    els.prompt.textContent = ui().prompt;
    renderLangbar();
    renderBoard();
    renderKeyboard();
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
