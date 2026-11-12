"""
Facade: the one entry point for turning JSON into a validated :class:`Deck`.

Pipeline::

    source -> read (size-capped) -> json.loads -> ParserRegistry (layout)
           -> CardValidator (each card) -> dedupe -> Deck

Thread safety: the loader itself holds no mutable state except an LRU cache
and an :class:`EventBus`, both guarded by locks. Everything it hands out
(``Deck``, ``Flashcard``, ``LoaderConfig``) is immutable, so one loader can be
shared by a thread pool.

Performance notes:

* File size is checked via ``stat`` *before* reading, so an oversized file
  costs one syscall rather than a multi-megabyte read.
* Parsed decks are cached by ``(resolved path, size, mtime_ns)``; an unchanged
  file is never re-parsed, a modified file is never served stale.
* Validation is a single pass with O(1) duplicate detection via a set.
"""

from __future__ import annotations

import json
import os
import re
import stat
import threading
from collections import OrderedDict
from pathlib import Path
from typing import (
    Any,
    Callable,
    Generic,
    Hashable,
    List,
    Optional,
    TextIO,
    TypeVar,
    Union,
)

from .config import LoaderConfig
from .events import EventBus, EventKind, LoadEvent
from .exceptions import (
    DeckTooLargeError,
    EmptyDeckError,
    FileAccessError,
    FileTooLargeError,
    FlashcardError,
    InvalidCardError,
    MalformedJSONError,
)
from .models import Deck, Flashcard
from .parsers import ParserRegistry
from .validators import CardValidator

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")

PathLike = Union[str, "os.PathLike[str]"]
# Anything that looks like "scheme://" is routed to the URL loader so that
# unsupported schemes (ftp://, file://) get a clear message instead of
# "file not found".
_URL_LIKE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


class LRUCache(Generic[K, V]):
    """Minimal thread-safe LRU cache with a hard capacity (no unbounded growth)."""

    __slots__ = ("_capacity", "_data", "_lock")

    def __init__(self, capacity: int) -> None:
        if capacity < 0:
            raise ValueError("capacity must be >= 0")
        self._capacity = capacity
        self._data: "OrderedDict[K, V]" = OrderedDict()
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def get(self, key: K) -> Optional[V]:
        with self._lock:
            value = self._data.get(key)
            if value is not None:
                self._data.move_to_end(key)
            return value

    def put(self, key: K, value: V) -> None:
        if self._capacity == 0:
            return
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._capacity:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


class FlashcardLoader:
    """Load and validate flashcard decks from files, strings, streams or URLs."""

    def __init__(
        self,
        config: Optional[LoaderConfig] = None,
        *,
        registry: Optional[ParserRegistry] = None,
        events: Optional[EventBus] = None,
    ) -> None:
        self._config = config or LoaderConfig()
        self._registry = registry or ParserRegistry()
        self._validator = CardValidator(self._config)
        self._events = events or EventBus()
        self._cache: LRUCache[tuple, Deck] = LRUCache(self._config.cache_size)

    # -- public attributes -------------------------------------------------

    @property
    def config(self) -> LoaderConfig:
        return self._config

    @property
    def events(self) -> EventBus:
        return self._events

    @property
    def registry(self) -> ParserRegistry:
        return self._registry

    @property
    def cache_size(self) -> int:
        """Number of decks currently cached."""
        return len(self._cache)

    def clear_cache(self) -> None:
        self._cache.clear()

    # -- entry points ------------------------------------------------------

    def load(self, source: PathLike) -> Deck:
        """Load from a local path or an ``http(s)://`` URL."""
        if isinstance(source, str) and _URL_LIKE.match(source):
            return self.load_url(source)
        return self.load_file(source)

    def load_file(self, path: PathLike) -> Deck:
        file_path = Path(path)
        source = str(file_path)
        try:
            info = file_path.stat()
        except FileNotFoundError:
            raise FileAccessError(f"Could not find the file {source!r}.") from None
        except PermissionError:
            raise FileAccessError(f"Permission denied reading {source!r}.") from None
        except OSError as exc:
            raise FileAccessError(
                f"Could not access {source!r}: {exc.strerror}."
            ) from None

        if stat.S_ISDIR(info.st_mode):
            raise FileAccessError(
                f"{source!r} is a directory, not a file.",
                hint="Pass the path to a .json file inside it.",
            )
        self._check_size(info.st_size, source)

        cache_key = (str(file_path.resolve()), info.st_size, info.st_mtime_ns)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._publish(
                EventKind.CACHE_HIT, f"Using cached deck for {source}", source
            )
            return cached

        try:
            with file_path.open("rb") as handle:
                content = handle.read(self._config.max_file_bytes + 1)
        except PermissionError:
            raise FileAccessError(f"Permission denied reading {source!r}.") from None
        except OSError as exc:
            raise FileAccessError(
                f"Could not read {source!r}: {exc.strerror}."
            ) from None

        self._check_size(len(content), source)
        try:
            text = content.decode(self._config.encoding)
        except UnicodeDecodeError:
            raise MalformedJSONError(
                f"The file {source!r} is not valid {self._config.encoding} text.",
                hint="Save the file as UTF-8, or set 'encoding' in the config.",
                source=source,
            ) from None

        deck = self._parse_string(text, source)
        self._cache.put(cache_key, deck)
        return deck

    def load_stream(self, stream: TextIO, *, source: str = "<stream>") -> Deck:
        """Load from an open text stream (e.g. ``sys.stdin``)."""
        text = stream.read(self._config.max_file_bytes + 1)
        return self.load_string(text, source=source)

    def load_url(
        self,
        url: str,
        *,
        fetcher: Optional[Callable[..., str]] = None,
    ) -> Deck:
        """Download a deck over HTTP(S) and load it."""
        from .remote import fetch_text  # local import keeps urllib optional

        fetch = fetcher or fetch_text
        text = fetch(
            url,
            timeout=self._config.request_timeout,
            max_bytes=self._config.max_file_bytes,
            encoding=self._config.encoding,
        )
        self._check_text_size(text, url, self._config.encoding)
        return self._parse_string(text, url)

    def load_string(self, text: str, *, source: str = "<string>") -> Deck:
        """Parse JSON text and build a validated deck."""
        if not isinstance(text, str):
            raise TypeError("text must be a str")
        self._check_text_size(text, source, "utf-8")
        return self._parse_string(text, source)

    def _parse_string(self, text: str, source: str) -> Deck:
        """Parse text whose encoded size has already been checked."""
        if not text.strip():
            raise MalformedJSONError(
                "The input is empty.",
                hint="A deck needs at least one card in JSON format.",
                source=source,
            )
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MalformedJSONError(
                f"Not valid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno}).",
                line=exc.lineno,
                column=exc.colno,
                source=source,
            ) from None
        return self.load_data(data, source=source)

    def load_data(self, data: Any, *, source: str = "<data>") -> Deck:
        """Validate already-parsed JSON (``dict``/``list``) into a deck."""
        try:
            return self._build_deck(data, source)
        except FlashcardError as exc:
            if exc.source is None:
                exc.source = source
            raise

    # -- internals ---------------------------------------------------------

    def _build_deck(self, data: Any, source: str) -> Deck:
        config = self._config
        parser, raw = self._registry.parse(data)
        self._publish(
            EventKind.FORMAT_DETECTED, f"Detected {parser.name} format", source
        )

        total = len(raw.items)
        if total > config.max_cards:
            raise DeckTooLargeError(
                f"The deck has {total} cards; the limit is {config.max_cards}."
            )

        cards: List[Flashcard] = []
        seen: Optional[set] = set() if config.dedupe else None
        skipped = 0
        duplicates = 0
        skip_invalid = config.on_invalid_card == "skip"
        validate = self._validator.validate

        for index, item in enumerate(raw.items):
            try:
                card = validate(item, index)
            except InvalidCardError as exc:
                if not skip_invalid:
                    raise
                skipped += 1
                self._publish(EventKind.CARD_SKIPPED, exc.message, source, index)
                continue
            if seen is not None:
                key = (card.front, card.back)
                if key in seen:
                    duplicates += 1
                    self._publish(
                        EventKind.DUPLICATE_REMOVED,
                        f"Card #{index + 1} duplicates an earlier card "
                        "and was removed.",
                        source,
                        index,
                    )
                    continue
                seen.add(key)
            cards.append(card)

        if not cards and not config.allow_empty:
            if total == 0:
                raise EmptyDeckError("The deck contains no cards.")
            raise EmptyDeckError(
                f"All {total} cards were skipped as invalid; nothing left to study.",
                hint="Fix the cards reported above, or remove --skip-invalid to see "
                "the first error in detail.",
            )

        deck = Deck(
            cards=tuple(cards),
            title=raw.title,
            source=source,
            format_name=parser.name,
            skipped=skipped,
            duplicates_removed=duplicates,
        )
        self._publish(
            EventKind.DECK_LOADED,
            f"Loaded {len(deck)} card(s) from {source} "
            f"({skipped} skipped, {duplicates} duplicates removed)",
            source,
        )
        return deck

    def _check_size(self, size: int, source: str) -> None:
        limit = self._config.max_file_bytes
        if size > limit:
            raise FileTooLargeError(
                f"The input is {size:,} bytes; the limit is {limit:,} bytes.",
                source=source,
            )

    def _check_text_size(self, text: str, source: str, encoding: str) -> None:
        try:
            size = len(text.encode(encoding))
        except UnicodeEncodeError:
            raise MalformedJSONError(
                f"The input contains text that cannot be encoded as {encoding}.",
                source=source,
            ) from None
        self._check_size(size, source)

    def _publish(
        self, kind: EventKind, message: str, source: str, index: Optional[int] = None
    ) -> None:
        self._events.publish(LoadEvent(kind, message, source, index))
