"""
Immutable domain models.

``Flashcard`` and ``Deck`` are frozen, slotted dataclasses. Immutability makes
them safe to share between threads and cache without copying, and ``slots``
keeps per-instance memory small for large decks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional, Tuple, Union, overload


@dataclass(frozen=True, slots=True)
class Flashcard:
    """A single question/answer pair."""

    front: str
    back: str
    hint: Optional[str] = None
    tags: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict, omitting unset optional fields."""
        data: Dict[str, Any] = {"front": self.front, "back": self.back}
        if self.hint is not None:
            data["hint"] = self.hint
        if self.tags:
            data["tags"] = list(self.tags)
        return data


@dataclass(frozen=True, slots=True)
class Deck:
    """An ordered, immutable collection of flashcards plus provenance info."""

    cards: Tuple[Flashcard, ...]
    title: Optional[str] = None
    source: str = "<memory>"
    format_name: str = "array"
    skipped: int = field(default=0, compare=False)
    duplicates_removed: int = field(default=0, compare=False)

    def __len__(self) -> int:
        return len(self.cards)

    def __iter__(self) -> Iterator[Flashcard]:
        return iter(self.cards)

    @overload
    def __getitem__(self, index: int) -> Flashcard: ...

    @overload
    def __getitem__(self, index: slice) -> Tuple[Flashcard, ...]: ...

    def __getitem__(
        self, index: Union[int, slice]
    ) -> Union[Flashcard, Tuple[Flashcard, ...]]:
        return self.cards[index]

    @property
    def all_tags(self) -> frozenset[str]:
        """Every distinct tag used across the deck."""
        return frozenset(tag for card in self.cards for tag in card.tags)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to the canonical *object format*."""
        data: Dict[str, Any] = {}
        if self.title is not None:
            data["title"] = self.title
        data["cards"] = [card.to_dict() for card in self.cards]
        return data
