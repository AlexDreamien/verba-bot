"""Tests for the message catalog."""

from __future__ import annotations

from bot.i18n import DEFAULT_LANG, LANGS, MESSAGES, t


def test_all_locales_share_the_same_keys():
    key_sets = {lang: set(MESSAGES[lang]) for lang in LANGS}
    reference = key_sets[DEFAULT_LANG]
    for lang in LANGS:
        assert key_sets[lang] == reference, f"locale {lang} has mismatched keys"


def test_default_language_is_ukrainian():
    assert DEFAULT_LANG == "uk"
    assert set(LANGS) == {"uk", "ru", "en"}


def test_t_formats_placeholders():
    assert "5" in t("broadcast_done", "en", ok=5, total=7)
    assert "7" in t("broadcast_done", "en", ok=5, total=7)


def test_t_falls_back_to_default_lang():
    # Unknown language falls back to the default-language catalog.
    assert t("play_button", "xx") == t("play_button", DEFAULT_LANG)


def test_t_unknown_key_returns_key():
    assert t("no_such_key", "en") == "no_such_key"
