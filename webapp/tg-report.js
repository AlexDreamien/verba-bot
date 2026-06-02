/*
 * Telegram Mini App reporting layer (MIT — original work).
 *
 * It does not touch the engine: it wraps the global `logEvent` the engine calls
 * and forwards outcomes to the bot's collector. Each event carries {lang, day}
 * (day is the Kyiv "d.mm.yyyy" key), so a player can play all three locales in a
 * day and each is reported independently:
 *
 *   game_started -> POST {backend}/api/started {initData, day, lang}
 *   game_success -> POST {backend}/api/result  {initData, day, lang, won, ...}
 *   game_failed  -> POST {backend}/api/result  {initData, day, lang, lost}
 *
 * Identity is the signed Telegram `initData`, validated server-side. Without a
 * backend URL or initData (e.g. opened in a plain browser) reporting is silently
 * disabled and the game still works.
 */
(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp;
  var backend = (window.VERBA_BACKEND_URL || "").replace(/\/+$/, "");
  var initData = tg && tg.initData ? tg.initData : "";
  var enabled = Boolean(backend && initData);

  function post(path, payload) {
    if (!enabled) return;
    try {
      fetch(backend + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(function () {});
    } catch (e) {
      /* non-fatal */
    }
  }

  function startKey(lang, day) {
    return "verba_tg_started_" + lang + "_" + day;
  }
  function reportedKey(lang, day) {
    return "verba_tg_reported_" + lang + "_" + day;
  }

  function startedAt(lang, day) {
    var v = parseInt(localStorage.getItem(startKey(lang, day)) || "0", 10);
    return v || 0;
  }

  function onStarted(d) {
    var key = startKey(d.lang, d.day);
    if (!localStorage.getItem(key)) {
      try {
        localStorage.setItem(key, String(Date.now()));
      } catch (e) {
        /* ignore */
      }
      post("/api/started", { initData: initData, day: d.day, lang: d.lang });
    }
  }

  function onResult(d, status) {
    var rkey = reportedKey(d.lang, d.day);
    if (localStorage.getItem(rkey) === "1") return;
    try {
      localStorage.setItem(rkey, "1");
    } catch (e) {
      /* ignore */
    }
    var payload = { initData: initData, day: d.day, lang: d.lang, status: status };
    if (status === "won") {
      payload.attempts = (typeof d.index === "number" ? d.index : 0) + 1;
      var start = startedAt(d.lang, d.day);
      payload.elapsed_ms = start ? Date.now() - start : null;
    } else {
      payload.attempts = 6;
      payload.elapsed_ms = null;
    }
    post("/api/result", payload);
  }

  var original = window.logEvent;
  window.logEvent = function (eventName, details) {
    try {
      var d = details || {};
      if (eventName === "game_started") onStarted(d);
      else if (eventName === "game_success") onResult(d, "won");
      else if (eventName === "game_failed") onResult(d, "lost");
    } catch (e) {
      /* never break the game */
    }
    if (typeof original === "function") return original.apply(this, arguments);
  };
})();
