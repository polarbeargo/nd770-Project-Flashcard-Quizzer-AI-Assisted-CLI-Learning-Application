"""Tests for per-card validation and normalisation."""

from __future__ import annotations

import pytest

from flashcards.config import LoaderConfig
from flashcards.exceptions import InvalidCardError
from flashcards.models import Flashcard
from flashcards.validators import CardValidator


@pytest.fixture
def validator() -> CardValidator:
    return CardValidator(
        LoaderConfig(max_field_length=20, max_tags=3, max_tag_length=5)
    )


class TestHappyPath:
    def test_minimal_card(self, validator: CardValidator):
        assert validator.validate({"front": "Q", "back": "A"}, 0) == Flashcard("Q", "A")

    def test_full_card_with_whitespace_normalised(self, validator: CardValidator):
        card = validator.validate(
            {
                "front": "  Q ",
                "back": "A\n",
                "hint": " h ",
                "tags": [" t1", "t2 ", "t1"],
            },
            0,
        )
        assert card == Flashcard("Q", "A", hint="h", tags=("t1", "t2"))

    def test_unknown_fields_are_ignored(self, validator: CardValidator):
        card = validator.validate({"front": "Q", "back": "A", "extra": [1, 2]}, 0)
        assert card.to_dict() == {"front": "Q", "back": "A"}

    def test_null_optionals_are_treated_as_absent(self, validator: CardValidator):
        card = validator.validate(
            {"front": "Q", "back": "A", "hint": None, "tags": None}, 0
        )
        assert card.hint is None and card.tags == ()

    def test_blank_hint_becomes_none(self, validator: CardValidator):
        assert (
            validator.validate({"front": "Q", "back": "A", "hint": "  "}, 0).hint
            is None
        )

    def test_tabs_and_newlines_allowed_inside_text(self, validator: CardValidator):
        card = validator.validate({"front": "a\tb\nc\r\nd", "back": "A"}, 0)
        assert card.front == "a\tb\nc\r\nd"

    def test_unicode_is_nfc_normalised(self, validator: CardValidator):
        decomposed = "e\u0301"  # e + combining acute
        card = validator.validate({"front": decomposed, "back": "A"}, 0)
        assert card.front == "\u00e9"

    def test_default_config_used_when_none_given(self):
        assert CardValidator().config == LoaderConfig()


class TestRejections:
    @pytest.mark.parametrize("item", ["text", 1, None, ["front", "back"], True])
    def test_non_object_item(self, validator: CardValidator, item):
        with pytest.raises(
            InvalidCardError, match="Card #3 must be a JSON object"
        ) as info:
            validator.validate(item, 2)
        assert info.value.index == 2

    @pytest.mark.parametrize("key", ["front", "back"])
    def test_missing_required_field(self, validator: CardValidator, key):
        item = {"front": "Q", "back": "A"}
        del item[key]
        with pytest.raises(
            InvalidCardError, match=f"missing the required '{key}'"
        ) as info:
            validator.validate(item, 0)
        assert info.value.field == key

    @pytest.mark.parametrize("value", ["", "   ", "\n\t"])
    def test_empty_required_field(self, validator: CardValidator, value):
        with pytest.raises(InvalidCardError, match="has an empty 'back'"):
            validator.validate({"front": "Q", "back": value}, 0)

    @pytest.mark.parametrize(
        "value, kind", [(1, "a number"), ([], "an array"), ({}, "an object")]
    )
    def test_wrong_type_field(self, validator: CardValidator, value, kind):
        with pytest.raises(InvalidCardError, match=f"'front' must be text, got {kind}"):
            validator.validate({"front": value, "back": "A"}, 0)

    def test_wrong_type_hint(self, validator: CardValidator):
        with pytest.raises(InvalidCardError, match="'hint' must be text"):
            validator.validate({"front": "Q", "back": "A", "hint": 7}, 0)

    def test_too_long_field(self, validator: CardValidator):
        with pytest.raises(InvalidCardError, match="too long") as info:
            validator.validate({"front": "x" * 21, "back": "A"}, 0)
        assert "max_field_length" in info.value.hint

    @pytest.mark.parametrize("bad", ["\x00", "\x1b[31mred", "\x7f", "\x0b"])
    def test_control_characters_rejected(self, validator: CardValidator, bad):
        with pytest.raises(InvalidCardError, match="control characters"):
            validator.validate({"front": f"Q{bad}", "back": "A"}, 0)

    def test_tags_must_be_list(self, validator: CardValidator):
        with pytest.raises(InvalidCardError, match="'tags' must be an array"):
            validator.validate({"front": "Q", "back": "A", "tags": "a,b"}, 0)

    def test_too_many_tags(self, validator: CardValidator):
        with pytest.raises(InvalidCardError, match="has 4 tags; limit is 3"):
            validator.validate(
                {"front": "Q", "back": "A", "tags": ["a", "b", "c", "d"]}, 0
            )

    def test_non_string_tag(self, validator: CardValidator):
        with pytest.raises(InvalidCardError, match="tag 2 must be text"):
            validator.validate({"front": "Q", "back": "A", "tags": ["a", 2]}, 0)

    @pytest.mark.parametrize("tag", ["toolong", "a\x00b"])
    def test_bad_tag_content(self, validator: CardValidator, tag):
        with pytest.raises(InvalidCardError, match="tag 1 is too long or contains"):
            validator.validate({"front": "Q", "back": "A", "tags": [tag]}, 0)

    def test_blank_tags_are_dropped(self, validator: CardValidator):
        card = validator.validate(
            {"front": "Q", "back": "A", "tags": ["", "  ", "ok"]}, 0
        )
        assert card.tags == ("ok",)


class TestErrorMetadataAndBoundaries:
    """Every rejection must identify the card index and offending field."""

    @pytest.mark.parametrize(
        "item, field",
        [
            ({"back": "A"}, "front"),
            ({"front": "Q"}, "back"),
            ({"front": "", "back": "A"}, "front"),
            ({"front": 1, "back": "A"}, "front"),
            ({"front": "Q", "back": "x" * 21}, "back"),
            ({"front": "Q", "back": "A", "hint": "\x00"}, "hint"),
            ({"front": "Q", "back": "A", "tags": "x"}, "tags"),
            ({"front": "Q", "back": "A", "tags": ["a", "b", "c", "d"]}, "tags"),
            ({"front": "Q", "back": "A", "tags": [1]}, "tags"),
            ({"front": "Q", "back": "A", "tags": ["toolong"]}, "tags"),
        ],
    )
    def test_index_and_field_are_reported(self, validator: CardValidator, item, field):
        with pytest.raises(InvalidCardError) as info:
            validator.validate(item, 7)
        assert (info.value.index, info.value.field) == (7, field)

    def test_non_object_reports_index_without_field(self, validator: CardValidator):
        with pytest.raises(InvalidCardError) as info:
            validator.validate("x", 3)
        assert (info.value.index, info.value.field) == (3, None)

    def test_field_exactly_at_length_limit_is_accepted(self, validator: CardValidator):
        card = validator.validate({"front": "x" * 20, "back": "A"}, 0)
        assert len(card.front) == 20

    def test_tag_exactly_at_length_limit_is_accepted(self, validator: CardValidator):
        card = validator.validate({"front": "Q", "back": "A", "tags": ["abcde"]}, 0)
        assert card.tags == ("abcde",)

    def test_tag_count_exactly_at_limit_is_accepted(self, validator: CardValidator):
        card = validator.validate(
            {"front": "Q", "back": "A", "tags": ["a", "b", "c"]}, 0
        )
        assert card.tags == ("a", "b", "c")
