"""Validate the engine's word lists in webapp/words.js.

The lists are authored by hand, so this guards against typos: every entry must
be exactly 5 letters drawn from its locale alphabet, and unique. It can't verify
that a word is "real", but it catches wrong-length / wrong-charset mistakes in CI.
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


def words_for(lang: str) -> list[str]:
    text = WORDS_JS.read_text(encoding="utf-8")
    match = re.search(rf"{lang}\s*:\s*\[(.*?)\]", text, re.S)
    assert match, f"locale {lang} not found in words.js"
    return re.findall(r'"([^"]+)"', match.group(1))


@pytest.mark.parametrize("lang", ["ru", "uk", "en"])
def test_word_list_present(lang):
    assert len(words_for(lang)) >= 20


@pytest.mark.parametrize("lang", ["ru", "uk", "en"])
def test_words_are_five_letters(lang):
    bad = [w for w in words_for(lang) if len(w) != 5]
    assert bad == [], f"{lang}: not 5 letters: {bad}"


@pytest.mark.parametrize("lang", ["ru", "uk", "en"])
def test_words_in_alphabet(lang):
    alphabet = ALPHABETS[lang]
    bad = [w for w in words_for(lang) if set(w) - alphabet]
    assert bad == [], f"{lang}: out-of-alphabet chars: {bad}"


@pytest.mark.parametrize("lang", ["ru", "uk", "en"])
def test_words_unique(lang):
    words = words_for(lang)
    dupes = sorted({w for w in words if words.count(w) > 1})
    assert dupes == [], f"{lang}: duplicates: {dupes}"
