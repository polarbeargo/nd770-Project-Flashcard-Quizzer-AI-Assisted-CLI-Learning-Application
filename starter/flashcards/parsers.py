"""
Strategy + Chain of Responsibility: detecting and unpacking deck layouts.

Each :class:`FormatParser` strategy knows how to recognise one top-level JSON
shape and turn it into a :class:`RawDeck` (an untyped list of card items plus
optional metadata). The :class:`ParserRegistry` walks its parsers in order
and hands the data to the first one that claims it.

Supported layouts:

* **Array format** - ``[{"front": "...", "back": "..."}, ...]``
* **Object format** - ``{"title": "...", "cards": [ ... ]}``

Adding a new layout means adding one small class and registering it; no
existing code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Protocol, Tuple, runtime_checkable

from .exceptions import UnsupportedFormatError


@dataclass(frozen=True, slots=True)
class RawDeck:
    """Unvalidated deck contents extracted from JSON."""

    items: List[Any]
    title: Optional[str] = None


@runtime_checkable
class FormatParser(Protocol):
    """Strategy interface for one deck layout."""

    name: str

    def can_parse(self, data: Any) -> bool:
        """Return ``True`` if this strategy should handle ``data``."""
        ...

    def parse(self, data: Any) -> RawDeck:
        """Extract card items; raise :class:`UnsupportedFormatError` if invalid."""
        ...


class ArrayFormatParser:
    """Handles a bare JSON array of card objects."""

    name = "array"

    def can_parse(self, data: Any) -> bool:
        return isinstance(data, list)

    def parse(self, data: Any) -> RawDeck:
        if not isinstance(data, list):  # defensive; registry guards this
            raise UnsupportedFormatError(
                f"Expected a JSON array, got {_describe(data)}."
            )
        return RawDeck(items=data)


class ObjectFormatParser:
    """Handles ``{"cards": [...]}`` with optional ``title``/``description``."""

    name = "object"
    CARDS_KEY = "cards"
    TITLE_KEYS = ("title", "name")

    def can_parse(self, data: Any) -> bool:
        return isinstance(data, dict)

    def parse(self, data: Any) -> RawDeck:
        if not isinstance(data, dict):  # defensive; registry guards this
            raise UnsupportedFormatError(
                f"Expected a JSON object, got {_describe(data)}."
            )
        if self.CARDS_KEY not in data:
            found = ", ".join(repr(k) for k in list(data)[:5]) or "none"
            raise UnsupportedFormatError(
                f"The top-level object is missing the required '{self.CARDS_KEY}' "
                f"key (found keys: {found})."
            )
        cards = data[self.CARDS_KEY]
        if not isinstance(cards, list):
            raise UnsupportedFormatError(
                f"'{self.CARDS_KEY}' must be a JSON array, got {_describe(cards)}."
            )
        title: Optional[str] = None
        for key in self.TITLE_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                title = value.strip()
                break
        return RawDeck(items=cards, title=title)


DEFAULT_PARSERS: Tuple[FormatParser, ...] = (
    ArrayFormatParser(),
    ObjectFormatParser(),
)


class ParserRegistry:
    """Immutable, ordered chain of :class:`FormatParser` strategies.

    Being immutable, a registry can be shared freely between threads;
    :meth:`register` returns a *new* registry rather than mutating.
    """

    __slots__ = ("_parsers",)

    def __init__(self, parsers: Optional[Iterable[FormatParser]] = None) -> None:
        chain = tuple(DEFAULT_PARSERS if parsers is None else parsers)
        for parser in chain:
            if not isinstance(parser, FormatParser):
                raise TypeError(f"{parser!r} does not implement FormatParser")
        self._parsers = chain

    @property
    def parsers(self) -> Tuple[FormatParser, ...]:
        return self._parsers

    @property
    def names(self) -> Tuple[str, ...]:
        return tuple(parser.name for parser in self._parsers)

    def register(
        self, parser: FormatParser, *, first: bool = False
    ) -> "ParserRegistry":
        """Return a new registry with ``parser`` appended (or prepended)."""
        chain = (parser, *self._parsers) if first else (*self._parsers, parser)
        return ParserRegistry(chain)

    def detect(self, data: Any) -> FormatParser:
        for parser in self._parsers:
            if parser.can_parse(data):
                return parser
        raise UnsupportedFormatError(
            f"The JSON top level is {_describe(data)}, which is not a deck layout."
        )

    def parse(self, data: Any) -> Tuple[FormatParser, RawDeck]:
        parser = self.detect(data)
        return parser, parser.parse(data)


_TYPE_NAMES = {
    dict: "an object",
    list: "an array",
    str: "a string",
    bool: "a boolean",
    int: "a number",
    float: "a number",
    type(None): "null",
}


def _describe(value: Any) -> str:
    """Return a JSON-flavoured description of a Python value for messages."""
    return _TYPE_NAMES.get(type(value), type(value).__name__)
