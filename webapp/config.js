// Deploy-time configuration for the Telegram Mini App integration.
//
// Set VERBA_BACKEND_URL to the public HTTPS origin of the result-collector
// backend (bot/web.py), e.g. "https://verba-api.example.com".
// Leave it empty to disable reporting (the game still works as a plain webapp).
//
// For local development, copy this file's value to point at your tunnel
// (cloudflared/ngrok) URL. This placeholder is committed; the real value is
// environment-specific.
window.VERBA_BACKEND_URL = "https://verba-bot.fly.dev";

// Set to true only after enabling inline mode for the bot in @BotFather
// (/setinline). When true, the "Share" button posts the result grid into any
// chat via Telegram's inline mode; otherwise it copies the grid to the clipboard.
window.VERBA_INLINE_SHARE = false;
