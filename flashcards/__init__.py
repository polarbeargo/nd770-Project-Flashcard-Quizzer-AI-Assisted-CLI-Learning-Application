"""
Flashcard loading, validation and export.

Quick start::

    from flashcards import FlashcardLoader

    deck = FlashcardLoader().load_file("data/samples/python_basics_array.json")
    for card in deck:
        print(card.front, "->", card.back)
"""

from __future__ import annotations

import logging

from .config import LoaderConfig
from .events import CollectingObserver, EventBus, EventKind, LoadEvent, log_event
from .exceptions import (
    ConfigError,
    DeckTooLargeError,
    EmptyDeckError,
    ExportError,
    FileAccessError,
    FileTooLargeError,
    FlashcardError,
    InvalidCardError,
    MalformedJSONError,
    RemoteFetchError,
    UnsupportedFormatError,
)
from .exporters import ExporterFactory, export_deck
from .loader import FlashcardLoader
from .models import Deck, Flashcard
from .parsers import ArrayFormatParser, ObjectFormatParser, ParserRegistry
from .validators import CardValidator

logging.getLogger(__name__).addHandler(logging.NullHandler())

__version__ = "1.0.0"

__all__ = [
    "ArrayFormatParser",
    "CardValidator",
    "CollectingObserver",
    "ConfigError",
    "Deck",
    "DeckTooLargeError",
    "EmptyDeckError",
    "EventBus",
    "EventKind",
    "ExportError",
    "ExporterFactory",
    "FileAccessError",
    "FileTooLargeError",
    "Flashcard",
    "FlashcardError",
    "FlashcardLoader",
    "InvalidCardError",
    "LoadEvent",
    "LoaderConfig",
    "MalformedJSONError",
    "ObjectFormatParser",
    "ParserRegistry",
    "RemoteFetchError",
    "UnsupportedFormatError",
    "export_deck",
    "log_event",
]
