"""
Observer pattern: a small thread-safe event bus.

The loader publishes :class:`LoadEvent` notifications (card skipped,
duplicate removed, deck loaded, ...) instead of printing or logging directly.
That keeps the loader free of UI concerns; the CLI, the logging layer and the
tests each subscribe with whatever behaviour they need.

Subscriptions return a :class:`Subscription` handle so callers can (and
should) unsubscribe, preventing the classic "observer list grows forever"
memory leak. ``Subscription`` also works as a context manager.
"""

from __future__ import annotations

import itertools
import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("flashcards.events")


class EventKind(str, Enum):
    """Categories of loader notifications."""

    FORMAT_DETECTED = "format_detected"
    CARD_SKIPPED = "card_skipped"
    DUPLICATE_REMOVED = "duplicate_removed"
    DECK_LOADED = "deck_loaded"
    CACHE_HIT = "cache_hit"


@dataclass(frozen=True, slots=True)
class LoadEvent:
    """An immutable notification emitted by the loader."""

    kind: EventKind
    message: str
    source: str = ""
    index: Optional[int] = None


Observer = Callable[[LoadEvent], None]


class Subscription:
    """Handle returned by :meth:`EventBus.subscribe`; call to cancel."""

    __slots__ = ("_bus", "_token", "_active")

    def __init__(self, bus: "EventBus", token: int) -> None:
        self._bus = bus
        self._token = token
        self._active = True

    @property
    def active(self) -> bool:
        return self._active

    def unsubscribe(self) -> None:
        if self._active:
            self._active = False
            self._bus._remove(self._token)

    def __enter__(self) -> "Subscription":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.unsubscribe()


class EventBus:
    """Thread-safe publish/subscribe hub.

    Observers are invoked synchronously on the publishing thread, *outside*
    the internal lock, so an observer may safely subscribe/unsubscribe during
    a callback. Exceptions raised by observers are logged and swallowed so a
    faulty listener can never break a load.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._observers: Dict[int, Observer] = {}
        self._tokens = itertools.count()

    def subscribe(self, observer: Observer) -> Subscription:
        if not callable(observer):
            raise TypeError("observer must be callable")
        with self._lock:
            token = next(self._tokens)
            self._observers[token] = observer
        return Subscription(self, token)

    def _remove(self, token: int) -> None:
        with self._lock:
            self._observers.pop(token, None)

    def clear(self) -> None:
        with self._lock:
            self._observers.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._observers)

    def publish(self, event: LoadEvent) -> None:
        with self._lock:
            if not self._observers:
                return
            snapshot: List[Observer] = list(self._observers.values())
        for observer in snapshot:
            try:
                observer(event)
            except Exception:  # noqa: BLE001 - isolate faulty observers
                logger.exception("Observer %r failed handling %s", observer, event.kind)


class CollectingObserver:
    """Observer that records events; handy for tests and summaries."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: List[LoadEvent] = []

    def __call__(self, event: LoadEvent) -> None:
        with self._lock:
            self._events.append(event)

    @property
    def events(self) -> List[LoadEvent]:
        with self._lock:
            return list(self._events)

    def of_kind(self, kind: EventKind) -> List[LoadEvent]:
        return [event for event in self.events if event.kind is kind]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


_LEVELS = {
    EventKind.FORMAT_DETECTED: logging.DEBUG,
    EventKind.CACHE_HIT: logging.DEBUG,
    EventKind.DECK_LOADED: logging.INFO,
    EventKind.DUPLICATE_REMOVED: logging.INFO,
    EventKind.CARD_SKIPPED: logging.WARNING,
}


def log_event(event: LoadEvent) -> None:
    """Observer that forwards events to the ``flashcards`` logger."""
    logger.log(_LEVELS.get(event.kind, logging.INFO), "%s", event.message)
