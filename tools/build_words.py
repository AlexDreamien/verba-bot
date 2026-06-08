#!/usr/bin/env python3
"""Generate webapp/words.js from open word-list sources.

Each locale gets two pools:

* ``answers``  — the daily-word pool (≈365, five DISTINCT letters). Seeded from a
  curated list (read back from the existing ``webapp/words.js`` so it is never
  lost) and auto-expanded with the most frequent words that are also hunspell
  lemmas — frequency keeps them common, the dictionary check filters out junk
  tokens, inflected forms, and proper names; a BLOCKLIST removes slurs/leftovers.
  For ru/uk the pool is restricted to **nouns in dictionary form** (pymorphy3):
  verbs/adverbs/adjectives stay guessable via ``accepted`` but are never the
  answer of the day. Install the optional deps for the filter:
  ``pip install pymorphy3 pymorphy3-dicts-ru pymorphy3-dicts-uk`` (without them
  the filter is a no-op and a warning is printed).
* ``accepted`` — a large dictionary of valid 5-letter words used ONLY to
  validate guesses (any real word is accepted, repeats allowed). It is the union
  of the external word lists, the hunspell lemmas, and the ``answers``.

Sources (cached under ``tools/_cache/`` after first download):

* en: dwyl/english-words ``words_alpha.txt`` — Unlicense (public domain).
* ru/uk/en frequency: hermitdave/FrequencyWords ``*_full.txt`` (OpenSubtitles
  2018) — CC BY-SA 4.0; used to rank/expand answers (and as the ru/uk accepted).
* ru/uk/en hunspell: LibreOffice dictionaries (CC BY-SA / similar) — used to
  validate answers and enrich ``accepted``.

Run:  python tools/build_words.py
"""

from __future__ import annotations

import re
import ssl
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORDS_JS = ROOT / "webapp" / "words.js"
CACHE = Path(__file__).resolve().parent / "_cache"

SOURCES = {
    "en": "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt",
    "ru": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/ru/ru_full.txt",
    "uk": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/uk/uk_full.txt",
}
# Hunspell dictionaries (LibreOffice). Merged into ``accepted`` AND used to
# validate auto-added answers: a frequency word only becomes an answer if it is
# a real dictionary lemma, which filters out junk tokens, inflected forms, and
# most proper names that a raw frequency list is full of.
HUNSPELL = {
    "ru": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ru_RU/ru_RU.dic",
    "uk": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/uk_UA/uk_UA.dic",
    "en": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_US.dic",
}

ALPHABETS = {
    "ru": set("абвгдежзийклмнопрстуфхцчшщъыьэюя"),
    "uk": set("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"),
    "en": set("abcdefghijklmnopqrstuvwxyz"),
}

# Frequency-ranked sources used to AUTO-EXPAND the answer pool with common words
# (ru/uk reuse the SOURCES frequency lists; en needs its own — words_alpha is
# alphabetical, not ranked). Only the most frequent 5-distinct-letter words are
# added, so answers stay common and guessable.
FREQ_SOURCES = {
    "ru": SOURCES["ru"],
    "uk": SOURCES["uk"],
    "en": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/en/en_full.txt",
}

# Target size of each locale's answer pool (≈ a year without repeats).
ANSWER_TARGET = 365

# Words never used as the daily answer (profanity / slurs). Best-effort, distinct
# 5-letter forms; extend as needed. ``ё`` is normalised to ``е`` for ru.
BLOCKLIST = {
    "ru": {
        "блядь",
        "мудак",
        "пизда",
        "хуево",
        "ебать",
        "сучка",
        "падла",
        "гниды",
        "шлюха",
        "сукин",
        # foreign first names that leak in from subtitle frequency
        "алекс",
        "джейн",
        "майкл",
        "фрэнк",
        "чарли",
        "генри",
        "питер",
    },
    "uk": {
        "блядь",
        "мудак",
        "пізда",
        "хуйло",
        "ебати",
        "сучка",
        "падла",
        "курва",
        "лайно",
        "сучий",
        "шлюха",
        "алекс",
        "майкл",
        "чарли",
        "чарлі",
    },
    "en": {
        "bitch",
        "whore",
        "fucks",
        "dicks",
        "cunts",
        "shite",
        "pussy",
        "twats",
        "chris",
        "frank",
        "james",
        "paris",
        "henry",
    },
}


def fetch(key: str, url: str, suffix: str = "txt") -> str:
    """Return the raw source text, using a cached copy when available."""
    CACHE.mkdir(exist_ok=True)
    cached = CACHE / f"{key}.{suffix}"
    if cached.exists():
        return cached.read_text(encoding="utf-8", errors="ignore")
    print(f"downloading {key}: {url}")
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(url, context=ctx, timeout=300) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            f"failed to download {key} ({exc}). Pre-download it to {cached} and re-run."
        ) from exc
    cached.write_text(data, encoding="utf-8")
    return data


def _norm(lang: str, word: str) -> str:
    word = word.strip().lower()
    return word.replace("ё", "е") if lang == "ru" else word


def freq_words(lang: str, text: str) -> set[str]:
    """5-letter words from a frequency list ('word count' per line)."""
    alphabet = ALPHABETS[lang]
    out: set[str] = set()
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        w = _norm(lang, parts[0])
        if len(w) == 5 and set(w) <= alphabet:
            out.add(w)
    return out


def hunspell_lemmas(lang: str, text: str) -> set[str]:
    """5-letter common-word lemmas from a hunspell .dic ('lemma/AFFIXFLAGS').

    Skips entries whose source form is capitalised — in these dictionaries that's
    how proper names and abbreviations are stored, and we never want those as
    answers (or, harmlessly, as accepted guesses).
    """
    alphabet = ALPHABETS[lang]
    out: set[str] = set()
    for line in text.splitlines():
        raw = line.split("/")[0].strip()
        if not raw or raw[:1] != raw[:1].lower():  # capitalised -> proper noun / abbr.
            continue
        w = _norm(lang, raw)
        if len(w) == 5 and set(w) <= alphabet:
            out.add(w)
    return out


def read_curated_answers() -> dict[str, list[str]]:
    """Extract the curated noun pool per locale from the current words.js."""
    text = WORDS_JS.read_text(encoding="utf-8")
    answers: dict[str, list[str]] = {}
    keys = list(re.finditer(r"^  (ru|uk|en):", text, re.M))
    for i, m in enumerate(keys):
        lang = m.group(1)
        end = keys[i + 1].start() if i + 1 < len(keys) else len(text)
        block = text[m.end() : end]
        arr = re.search(r"answers\s*:\s*\[(.*?)\]", block, re.S) or re.search(
            r"\[(.*?)\]", block, re.S
        )
        answers[lang] = re.findall(r'"([^"]+)"', arr.group(1)) if arr else []
    return answers


def unique_letters(words: list[str]) -> list[str]:
    """Keep only valid 5-letter words whose letters are all distinct."""
    return sorted({w for w in words if len(w) == 5 and len(set(w)) == 5})


def freq_ranked(lang: str, text: str) -> list[str]:
    """5-distinct-letter words from a frequency list, most frequent first.

    Preserves the source order (frequency lists are pre-sorted) and de-duplicates,
    so the head of the list is the most common, most "answerable" vocabulary.
    """
    alphabet = ALPHABETS[lang]
    out: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        w = _norm(lang, parts[0])
        if len(w) == 5 and len(set(w)) == 5 and set(w) <= alphabet and w not in seen:
            seen.add(w)
            out.append(w)
    return out


# POS filter: only NOUNS are used as daily answers for ru/uk (verbs, adverbs,
# adjectives stay guessable via ``accepted`` but are never the word of the day).
# Uses pymorphy3 + dicts (build-time only: pip install pymorphy3 pymorphy3-dicts-ru
# pymorphy3-dicts-uk). If unavailable, the filter is a no-op (all words kept) and
# a warning is printed.
_MORPH: dict[str, object] = {}


def _noun_checker(lang: str):
    """Return ``is_noun(word) -> bool`` for ru/uk; an accept-all for other langs."""
    if lang not in ("ru", "uk"):
        return lambda _w: True
    if lang not in _MORPH:
        try:
            import pymorphy3

            _MORPH[lang] = pymorphy3.MorphAnalyzer(lang=lang)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully without the dep
            print(f"{lang}: NOUN filter DISABLED (pymorphy3 unavailable: {exc})")
            _MORPH[lang] = None
    morph = _MORPH[lang]
    if morph is None:
        return lambda _w: True

    # Require the word to be a noun in its DICTIONARY form (normal_form == word):
    # this keeps base nouns ("вагон") but rejects oblique forms that merely look
    # like adverbs ("рядом" = instr. of "ряд", "разом" = instr. of "раз").
    def is_noun(w: str) -> bool:
        return any(p.tag.POS == "NOUN" and p.normal_form == w for p in morph.parse(w))

    return is_noun


def expand_answers(lang: str, curated: list[str], lemmas: set[str]) -> list[str]:
    """Noun answers: curated + the most frequent dictionary *nouns*, up to target.

    A candidate must be a hunspell lemma (filters junk/inflections/names) and, for
    ru/uk, a NOUN (verbs/adverbs/adjectives are excluded from the daily pool but
    remain in ``accepted``).
    """
    is_noun = _noun_checker(lang)
    block = BLOCKLIST.get(lang, set())
    answers: list[str] = []
    seen: set[str] = set()
    kept_curated = 0
    for w in curated:
        if w in seen:
            continue
        seen.add(w)
        if is_noun(w):
            answers.append(w)
            kept_curated += 1

    # ru/uk reuse the already-cached frequency lists (keys "ru"/"uk"); en's main
    # cache is words_alpha (not ranked), so its frequency list needs its own key.
    cache_key = "en_freq" if lang == "en" else lang
    try:
        ranked = freq_ranked(lang, fetch(cache_key, FREQ_SOURCES[lang]))
    except SystemExit as exc:  # network unavailable — keep the curated pool
        print(f"{lang}: freq expansion skipped ({exc})")
        ranked = []
    added = 0
    for w in ranked:
        if len(answers) >= ANSWER_TARGET:
            break
        if w in seen or w in block or (lemmas and w not in lemmas):
            continue
        seen.add(w)
        if is_noun(w):
            answers.append(w)
            added += 1
    print(f"{lang}: curated_nouns={kept_curated} +auto_nouns={added} -> answers={len(answers)}")
    return sorted(answers)


def render_array(words: list[str], indent: str, per_line: int = 12) -> str:
    lines = []
    for i in range(0, len(words), per_line):
        chunk = ", ".join(f'"{w}"' for w in words[i : i + per_line])
        lines.append(f"{indent}{chunk},")
    return "\n".join(lines)


def main() -> None:
    curated = read_curated_answers()
    blocks = []
    for lang in ("ru", "uk", "en"):
        lemmas = (
            hunspell_lemmas(lang, fetch(f"{lang}_hunspell", HUNSPELL[lang], "dic"))
            if lang in HUNSPELL
            else set()
        )
        answers = expand_answers(lang, unique_letters(curated.get(lang, [])), lemmas)
        accepted_set = freq_words(lang, fetch(lang, SOURCES[lang]))
        accepted_set |= lemmas
        accepted_set |= set(answers)  # every answer must be guessable
        accepted = sorted(accepted_set)
        print(f"{lang}: answers={len(answers)} (unique-letter) accepted={len(accepted)}")
        blocks.append(
            f"  {lang}: {{\n"
            f"    answers: [\n{render_array(answers, '      ')}\n    ],\n"
            f"    accepted: [\n{render_array(accepted, '      ')}\n    ],\n"
            f"  }},"
        )
    header = (
        "/*\n"
        " * Daily-word pools for the engine, one entry per locale, GENERATED by\n"
        " * tools/build_words.py — do not edit by hand.\n"
        " *\n"
        " *   answers  — daily-word pool: curated nouns with five DISTINCT letters.\n"
        " *   accepted — large dictionary of valid 5-letter words; a guess is only\n"
        " *              accepted if it is in this set (answers are always included).\n"
        " *\n"
        " * Word data: en dwyl/english-words (Unlicense); ru/uk hermitdave/\n"
        " * FrequencyWords + uk LibreOffice/brown-uk hunspell (CC BY-SA 4.0). See\n"
        " * NOTICE.md. Engine code is MIT.\n"
        " */\n"
    )
    body = "window.VERBA_WORDS = {\n" + "\n".join(blocks) + "\n};\n"
    WORDS_JS.write_text(header + body, encoding="utf-8")
    print(f"wrote {WORDS_JS} ({WORDS_JS.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    sys.exit(main())
