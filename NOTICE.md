# Credits

Verba is a daily 5-letter word-guessing game in the spirit of classic puzzles
like Wordle. It is **original work** and bundles **no third-party code or word
data**:

- `engine.js` — a from-scratch word-guessing engine (rendering, on-screen
  keyboard, duplicate-letter coloring, daily word selection, language switch);
- `words.js` — hand-curated 5-letter word lists (ru / uk / en) authored for
  this project;
- `styles.css`, `index.html`, `config.js`, `tg-report.js` — original.

The whole repository is therefore MIT-licensed (see `LICENSE`) with no bundled
third-party dependencies. (At runtime the Mini App loads Telegram's official
`telegram-web-app.js` from telegram.org.)
