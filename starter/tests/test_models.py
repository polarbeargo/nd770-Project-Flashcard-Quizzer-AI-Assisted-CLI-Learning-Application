"""Tests for the immutable Flashcard / Deck models."""

from __future__ import annotations

import dataclasses

import pytest

from flashcards.models import Deck, Flashcard


class TestFlashcard:
    def test_minimal_card_to_dict_omits_optionals(self):
        card = Flashcard("Q", "A")
        assert card.to_dict() == {"front": "Q", "back": "A"}

    def test_full_card_to_dict_includes_hint_and_tags(self):
        card = Flashcard("Q", "A", hint="h", tags=("x", "y"))
        assert card.to_dict() == {
            "front": "Q",
            "back": "A",
            "hint": "h",
            "tags": ["x", "y"],
        }

    def test_card_is_immutable(self):
        card = Flashcard("Q", "A")
        with pytest.raises(dataclasses.FrozenInstanceError):
            card.front = "changed"  # type: ignore[misc]

    def test_card_uses_slots(self):
        card = Flashcard("Q", "A")
        assert not hasattr(card, "__dict__")
        # Frozen+slots dataclasses raise FrozenInstanceError for known fields;
        # for unknown names CPython may surface TypeError from the generated
        # __setattr__ - either way, nothing can be attached to the instance.
        with pytest.raises((AttributeError, TypeError)):
            card.extra = 1  # type: ignore[attr-defined]
        assert not hasattr(card, "extra")

    def test_cards_are_hashable_and_comparable(self):
        assert Flashcard("Q", "A") == Flashcard("Q", "A")
        assert len({Flashcard("Q", "A"), Flashcard("Q", "A")}) == 1


class TestDeck:
    @pytest.fixture
    def deck(self) -> Deck:
        return Deck(
            cards=(
                Flashcard("Q1", "A1", tags=("a",)),
                Flashcard("Q2", "A2", tags=("b", "a")),
            ),
            title="T",
            source="mem",
            format_name="object",
        )

    def test_len_iter_getitem(self, deck: Deck):
        assert len(deck) == 2
        assert [c.front for c in deck] == ["Q1", "Q2"]
        assert deck[0].front == "Q1"
        assert deck[-1].back == "A2"
        assert deck[0:1] == (deck[0],)

    def test_all_tags_is_distinct_set(self, deck: Deck):
        assert deck.all_tags == frozenset({"a", "b"})

    def test_to_dict_is_object_format(self, deck: Deck):
        data = deck.to_dict()
        assert list(data) == ["title", "cards"]
        assert data["cards"][1]["tags"] == ["b", "a"]

    def test_to_dict_without_title(self):
        assert Deck(cards=()).to_dict() == {"cards": []}

    def test_statistics_do_not_affect_equality(self):
        a = Deck(cards=(), skipped=0, duplicates_removed=0)
        b = Deck(cards=(), skipped=5, duplicates_removed=2)
        assert a == b

    def test_empty_deck_is_falsy(self):
        assert not Deck(cards=())
        assert Deck(cards=(Flashcard("Q", "A"),))
