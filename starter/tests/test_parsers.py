"""Tests for format-detection strategies and the parser registry."""

from __future__ import annotations

import pytest

from flashcards.exceptions import UnsupportedFormatError
from flashcards.parsers import (
    ArrayFormatParser,
    ObjectFormatParser,
    ParserRegistry,
    RawDeck,
    _describe,
)


class TestArrayFormatParser:
    def test_claims_lists_only(self):
        parser = ArrayFormatParser()
        assert parser.can_parse([]) is True
        assert parser.can_parse({}) is False
        assert parser.can_parse("x") is False

    def test_parse_returns_items_without_title(self):
        raw = ArrayFormatParser().parse([{"a": 1}])
        assert raw == RawDeck(items=[{"a": 1}], title=None)

    def test_parse_rejects_non_list_defensively(self):
        with pytest.raises(UnsupportedFormatError, match="Expected a JSON array"):
            ArrayFormatParser().parse({"cards": []})


class TestObjectFormatParser:
    def test_claims_dicts_only(self):
        parser = ObjectFormatParser()
        assert parser.can_parse({}) is True
        assert parser.can_parse([]) is False

    def test_parse_extracts_cards_and_title(self):
        raw = ObjectFormatParser().parse({"title": "  T ", "cards": [1, 2]})
        assert raw.items == [1, 2] and raw.title == "T"

    def test_name_is_fallback_title(self):
        raw = ObjectFormatParser().parse({"name": "N", "cards": []})
        assert raw.title == "N"

    def test_blank_or_non_string_title_ignored(self):
        assert ObjectFormatParser().parse({"title": "  ", "cards": []}).title is None
        assert ObjectFormatParser().parse({"title": 5, "cards": []}).title is None

    def test_missing_cards_key_lists_found_keys(self):
        with pytest.raises(UnsupportedFormatError) as info:
            ObjectFormatParser().parse({"deck": [], "x": 1})
        assert "missing the required 'cards' key" in str(info.value)
        assert "'deck'" in str(info.value)

    def test_missing_cards_on_empty_object(self):
        with pytest.raises(UnsupportedFormatError, match="found keys: none"):
            ObjectFormatParser().parse({})

    def test_cards_not_a_list(self):
        with pytest.raises(
            UnsupportedFormatError, match="must be a JSON array, got a string"
        ):
            ObjectFormatParser().parse({"cards": "nope"})

    def test_parse_rejects_non_dict_defensively(self):
        with pytest.raises(UnsupportedFormatError, match="Expected a JSON object"):
            ObjectFormatParser().parse([])


class TestParserRegistry:
    def test_default_chain_order(self):
        assert ParserRegistry().names == ("array", "object")

    def test_detect_routes_to_correct_strategy(self):
        registry = ParserRegistry()
        assert registry.detect([]).name == "array"
        assert registry.detect({"cards": []}).name == "object"

    @pytest.mark.parametrize("data", ["text", 42, 3.5, True, None])
    def test_detect_rejects_scalars(self, data):
        with pytest.raises(UnsupportedFormatError, match="not a deck layout"):
            ParserRegistry().detect(data)

    def test_parse_returns_parser_and_raw_deck(self):
        parser, raw = ParserRegistry().parse({"cards": [{"front": "Q"}]})
        assert parser.name == "object" and raw.items == [{"front": "Q"}]

    def test_register_is_non_mutating(self):
        class StringParser:
            name = "string"

            def can_parse(self, data):
                return isinstance(data, str)

            def parse(self, data):
                return RawDeck(items=[{"front": data, "back": data}])

        base = ParserRegistry()
        extended = base.register(StringParser())
        assert base.names == ("array", "object")
        assert extended.names == ("array", "object", "string")
        assert extended.detect("hello").name == "string"

        prepended = base.register(StringParser(), first=True)
        assert prepended.names[0] == "string"

    def test_rejects_objects_that_are_not_parsers(self):
        with pytest.raises(TypeError):
            ParserRegistry([object()])  # type: ignore[list-item]

    def test_parsers_property_exposes_chain(self):
        registry = ParserRegistry()
        assert isinstance(registry.parsers[0], ArrayFormatParser)


@pytest.mark.parametrize(
    "value, expected",
    [
        ({}, "an object"),
        ([], "an array"),
        ("s", "a string"),
        (True, "a boolean"),
        (1, "a number"),
        (1.5, "a number"),
        (None, "null"),
        (object(), "object"),
    ],
)
def test_describe(value, expected):
    assert _describe(value) == expected


def test_missing_cards_message_lists_at_most_five_keys():
    data = {f"k{i}": i for i in range(7)}
    with pytest.raises(UnsupportedFormatError) as info:
        ObjectFormatParser().parse(data)
    message = str(info.value)
    assert all(f"'k{i}'" in message for i in range(5))
    assert "'k5'" not in message and "'k6'" not in message
