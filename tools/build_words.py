#!/usr/bin/env python3
"""Generate webapp/words.js from open word-list sources.

Each locale gets two pools:

* ``answers``  — the daily-word pool: curated common nouns, filtered to words
  with **five distinct letters** (no repeats). The curated nouns are read back
  from the existing ``webapp/words.js`` so they are never lost on regeneration.
* ``accepted`` — a large dictionary of valid 5-letter words used ONLY to
  validate guesses (any real word is accepted, repeats allowed). It is the union
  of the external word lists and the ``answers`` (every answer is guessable).

Sources (cached under ``tools/_cache/`` after first download):

* en: dwyl/english-words ``words_alpha.txt`` — Unlicense (public domain).
* ru/uk: hermitdave/FrequencyWords ``*_full.txt`` (OpenSubtitles 2018) — CC BY-SA 4.0.
* uk (extra): LibreOffice ``uk_UA.dic`` (hunspell, brown-uk/VESUM) — CC BY-SA 4.0,
  merged in to cover words missing from the subtitle corpus (e.g. "дерун").

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
# Extra hunspell dictionaries merged into ``accepted`` (lemmas only).
HUNSPELL = {
    "uk": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/uk_UA/uk_UA.dic",
}

ALPHABETS = {
    "ru": set("абвгдежзийклмнопрстуфхцчшщъыьэюя"),
    "uk": set("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"),
    "en": set("abcdefghijklmnopqrstuvwxyz"),
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
    """5-letter lemmas from a hunspell .dic ('lemma/AFFIXFLAGS' per line)."""
    alphabet = ALPHABETS[lang]
    out: set[str] = set()
    for line in text.splitlines():
        w = _norm(lang, line.split("/")[0])
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
        answers = unique_letters(curated.get(lang, []))
        accepted_set = freq_words(lang, fetch(lang, SOURCES[lang]))
        if lang in HUNSPELL:
            accepted_set |= hunspell_lemmas(lang, fetch(f"{lang}_hunspell", HUNSPELL[lang], "dic"))
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
