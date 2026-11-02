"""
User-facing exception hierarchy for the flashcard loader.

Every exception here carries a human-friendly ``message`` plus an optional
``hint`` so the CLI can explain *what* went wrong and *how to fix it* without
ever exposing a raw Python traceback to the user.
"""

from __future__ import annotations

from typing import Optional


class FlashcardError(Exception):
    """Base class for all errors the application reports to the user."""

    default_hint: str = ""

    def __init__(
        self,
        message: str,
        *,
        hint: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = self.default_hint if hint is None else hint
        self.source = source

    def user_message(self) -> str:
        """Return a formatted, multi-line message suitable for printing."""
        prefix = f"In {self.source!r}: " if self.source else ""
        text = f"{prefix}{self.message}"
        if self.hint:
            text += f"\n  Hint: {self.hint}"
        return text

    def __str__(self) -> str:
        return self.message


class ConfigError(FlashcardError):
    """Raised when loader configuration values are invalid."""

    default_hint = "Check the configuration file or FLASHCARD_* environment variables."


class FileAccessError(FlashcardError):
    """Raised when the deck file cannot be found or opened."""

    default_hint = "Check that the path is correct and that you have read permission."


class FileTooLargeError(FlashcardError):
    """Raised when input exceeds the configured size budget."""

    default_hint = (
        "Split the deck into smaller files or raise 'max_file_bytes' in the config."
    )


class MalformedJSONError(FlashcardError):
    """Raised when the input text is not valid JSON."""

    default_hint = (
        "Look for missing commas, unmatched brackets/braces, trailing commas, "
        "or unquoted keys. An online JSON validator can pinpoint the problem."
    )

    def __init__(
        self,
        message: str,
        *,
        line: Optional[int] = None,
        column: Optional[int] = None,
        hint: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        super().__init__(message, hint=hint, source=source)
        self.line = line
        self.column = column


class UnsupportedFormatError(FlashcardError):
    """Raised when JSON parses but is not in a recognised deck layout."""

    default_hint = (
        'Use either an array: [{"front": "...", "back": "..."}] '
        'or an object: {"cards": [{"front": "...", "back": "..."}]}.'
    )


class InvalidCardError(FlashcardError):
    """Raised when an individual card is missing fields or has bad values."""

    default_hint = (
        'Every card needs non-empty string "front" and "back" fields. '
        'Optional: "hint" (string) and "tags" (list of strings).'
    )

    def __init__(
        self,
        message: str,
        *,
        index: int,
        field: Optional[str] = None,
        hint: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        super().__init__(message, hint=hint, source=source)
        self.index = index
        self.field = field


class EmptyDeckError(FlashcardError):
    """Raised when a deck contains no usable cards."""

    default_hint = "Add at least one card, or pass --allow-empty if this is intended."


class DeckTooLargeError(FlashcardError):
    """Raised when a deck has more cards than the configured limit."""

    default_hint = "Split the deck or raise 'max_cards' in the config."


class RemoteFetchError(FlashcardError):
    """Raised when a deck cannot be downloaded from a URL."""

    default_hint = "Check the URL, your network connection, and that the server is up."


class ExportError(FlashcardError):
    """Raised when a deck cannot be exported."""

    default_hint = "Check the output path is writable and the format is supported."
