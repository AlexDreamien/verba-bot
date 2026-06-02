"""Validate the engine's word pools in webapp/words.js.

Each locale has two arrays: ``answers`` (curated daily-word pool) and
``accepted`` (large guess dictionary). Both must contain only unique 5-letter
words of the locale alphabet, every answer must also be accepted, and the
accepted dictionary must be large enough to make the game playable.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORDS_JS = Path(__file__).resolve().parents[1] / "webapp" / "words.js"

ALPHABETS = {
    "ru": set("абвгдежзийклмнопрстуфхцчшщъыьэюя"),
    "uk": set("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"),
    "en": set("abcdefghijklmnopqrstuvwxyz"),
}
LANGS = ("ru", "uk", "en")
POOLS = ("answers", "accepted")


def _block(lang: str) -> str:
    text = WORDS_JS.read_text(encoding="utf-8")
    keys = list(re.finditer(r"^  (ru|uk|en):", text, re.M))
    for i, m in enumerate(keys):
        if m.group(1) == lang:
            end = keys[i + 1].start() if i + 1 < len(keys) else len(text)
            return text[m.end() : end]
    return ""


def words(lang: str, pool: str) -> list[str]:
    m = re.search(rf"{pool}\s*:\s*\[(.*?)\]", _block(lang), re.S)
    assert m, f"{lang}.{pool} not found"
    return re.findall(r'"([^"]+)"', m.group(1))


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("pool", POOLS)
def test_words_are_five_letters(lang, pool):
    bad = [w for w in words(lang, pool) if len(w) != 5]
    assert bad == [], f"{lang}.{pool}: not 5 letters: {bad[:10]}"


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("pool", POOLS)
def test_words_in_alphabet(lang, pool):
    alphabet = ALPHABETS[lang]
    bad = [w for w in words(lang, pool) if set(w) - alphabet]
    assert bad == [], f"{lang}.{pool}: out-of-alphabet chars: {bad[:10]}"


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("pool", POOLS)
def test_words_unique(lang, pool):
    ws = words(lang, pool)
    dupes = sorted({w for w in ws if ws.count(w) > 1})
    assert dupes == [], f"{lang}.{pool}: duplicates: {dupes[:10]}"


@pytest.mark.parametrize("lang", LANGS)
def test_answers_subset_of_accepted(lang):
    missing = set(words(lang, "answers")) - set(words(lang, "accepted"))
    assert missing == set(), f"{lang}: answers missing from accepted: {sorted(missing)[:10]}"


@pytest.mark.parametrize("lang", LANGS)
def test_pools_are_substantial(lang):
    assert len(words(lang, "answers")) >= 100
    assert len(words(lang, "accepted")) >= 1000
