"""Tests for the exception hierarchy and friendly message formatting."""

from __future__ import annotations

import pytest

from flashcards import exceptions as exc


def test_user_message_includes_default_hint():
    error = exc.FileAccessError("Could not find it.")
    text = error.user_message()
    assert text.startswith("Could not find it.")
    assert "Hint:" in text and "read permission" in text


def test_user_message_prefixes_source_when_set():
    error = exc.EmptyDeckError("No cards.", source="deck.json")
    assert error.user_message().startswith("In 'deck.json': No cards.")


def test_custom_hint_overrides_default():
    error = exc.InvalidCardError("bad", index=0, hint="custom")
    assert error.hint == "custom"
    assert error.user_message().endswith("Hint: custom")


def test_empty_hint_suppresses_hint_line():
    error = exc.FlashcardError("plain", hint="")
    assert error.user_message() == "plain"


def test_str_is_plain_message():
    assert str(exc.ConfigError("oops")) == "oops"


def test_malformed_json_carries_position():
    error = exc.MalformedJSONError("bad", line=3, column=7)
    assert (error.line, error.column) == (3, 7)


def test_invalid_card_carries_index_and_field():
    error = exc.InvalidCardError("bad", index=4, field="back")
    assert (error.index, error.field) == (4, "back")


@pytest.mark.parametrize(
    "cls",
    [
        exc.ConfigError,
        exc.FileAccessError,
        exc.FileTooLargeError,
        exc.MalformedJSONError,
        exc.UnsupportedFormatError,
        exc.EmptyDeckError,
        exc.DeckTooLargeError,
        exc.RemoteFetchError,
        exc.ExportError,
    ],
)
def test_all_errors_derive_from_flashcard_error(cls):
    assert issubclass(cls, exc.FlashcardError)
    assert cls.default_hint


def test_malformed_json_keeps_custom_hint_and_source():
    error = exc.MalformedJSONError("bad", hint="fix it", source="x.json")
    assert error.hint == "fix it" and error.source == "x.json"
    assert error.user_message() == "In 'x.json': bad\n  Hint: fix it"


def test_base_exception_args_hold_the_message():
    error = exc.FlashcardError("something")
    assert error.args == ("something",)
    assert repr(error) == "FlashcardError('something')"
