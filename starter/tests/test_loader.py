"""Tests for the FlashcardLoader facade and its LRU cache."""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pytest

from flashcards import (
    CollectingObserver,
    DeckTooLargeError,
    EmptyDeckError,
    EventKind,
    FileAccessError,
    FileTooLargeError,
    FlashcardLoader,
    InvalidCardError,
    LoaderConfig,
    MalformedJSONError,
    UnsupportedFormatError,
)
from flashcards.loader import LRUCache
from flashcards.parsers import ParserRegistry, RawDeck

from .conftest import ARRAY_DECK, OBJECT_DECK

# --------------------------------------------------------------------------- #
# LRU cache
# --------------------------------------------------------------------------- #


class TestLRUCache:
    def test_put_get_and_eviction_order(self):
        cache: LRUCache[str, int] = LRUCache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        assert cache.get("a") == 1  # touch "a" so "b" becomes LRU
        cache.put("c", 3)
        assert cache.get("b") is None
        assert cache.get("a") == 1 and cache.get("c") == 3
        assert len(cache) == 2 and cache.capacity == 2

    def test_zero_capacity_never_stores(self):
        cache: LRUCache[str, int] = LRUCache(0)
        cache.put("a", 1)
        assert cache.get("a") is None and len(cache) == 0

    def test_negative_capacity_rejected(self):
        with pytest.raises(ValueError):
            LRUCache(-1)

    def test_clear(self):
        cache: LRUCache[str, int] = LRUCache(3)
        cache.put("a", 1)
        cache.clear()
        assert len(cache) == 0


# --------------------------------------------------------------------------- #
# Formats
# --------------------------------------------------------------------------- #


class TestFormats:
    def test_array_format(self):
        deck = FlashcardLoader().load_data(ARRAY_DECK)
        assert len(deck) == 2
        assert deck.format_name == "array" and deck.title is None
        assert deck[1].tags == ("t1", "t2")

    def test_object_format(self):
        deck = FlashcardLoader().load_data(OBJECT_DECK)
        assert len(deck) == 2
        assert deck.format_name == "object" and deck.title == "Demo"

    def test_sample_files_load(self, samples_dir: Path):
        loader = FlashcardLoader()
        assert len(loader.load_file(samples_dir / "python_basics_array.json")) == 5
        deck = loader.load_file(samples_dir / "design_patterns_object.json")
        assert deck.title == "Design Patterns" and len(deck) == 5

    def test_round_trip_through_to_dict(self):
        loader = FlashcardLoader()
        first = loader.load_data(OBJECT_DECK)
        second = loader.load_data(first.to_dict())
        assert first.cards == second.cards and first.title == second.title

    def test_custom_registry_is_honoured(self):
        class CsvLikeParser:
            name = "csvlike"

            def can_parse(self, data):
                return isinstance(data, str)

            def parse(self, data):
                front, back = data.split("|")
                return RawDeck(items=[{"front": front, "back": back}])

        registry = ParserRegistry().register(CsvLikeParser())
        loader = FlashcardLoader(registry=registry)
        assert loader.registry is registry
        deck = loader.load_data("Q|A")
        assert deck.format_name == "csvlike" and deck[0].back == "A"


# --------------------------------------------------------------------------- #
# Error handling
# --------------------------------------------------------------------------- #


class TestErrors:
    def test_malformed_json_reports_position_and_source(self, write_json):
        path = write_json('[{"front": "Q" "back": "A"}]')
        with pytest.raises(MalformedJSONError) as info:
            FlashcardLoader().load_file(path)
        err = info.value
        assert (err.line, err.column) == (1, 16)
        assert "line 1, column 16" in err.message
        assert err.source == str(path)
        assert "Not valid JSON" in err.user_message()

    def test_malformed_sample_file(self, samples_dir: Path):
        with pytest.raises(MalformedJSONError):
            FlashcardLoader().load_file(samples_dir / "invalid_malformed.json")

    @pytest.mark.parametrize("text", ["", "   \n\t"])
    def test_empty_input(self, text):
        with pytest.raises(MalformedJSONError, match="empty"):
            FlashcardLoader().load_string(text)

    def test_non_string_input_is_programming_error(self):
        with pytest.raises(TypeError):
            FlashcardLoader().load_string(b"[]")  # type: ignore[arg-type]

    def test_missing_field_in_strict_mode_raises_with_source(self):
        with pytest.raises(InvalidCardError) as info:
            FlashcardLoader().load_data([{"front": "Q"}], source="deck.json")
        assert info.value.source == "deck.json"
        assert "Card #1 is missing the required 'back'" in str(info.value)

    def test_unsupported_top_level(self):
        with pytest.raises(UnsupportedFormatError, match="not a deck layout"):
            FlashcardLoader().load_string('"just a string"')

    def test_object_without_cards_key(self):
        with pytest.raises(
            UnsupportedFormatError, match="missing the required 'cards'"
        ):
            FlashcardLoader().load_data({"deck": []})

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileAccessError, match="Could not find"):
            FlashcardLoader().load_file(tmp_path / "missing.json")

    def test_directory_rejected(self, tmp_path: Path):
        with pytest.raises(FileAccessError, match="is a directory"):
            FlashcardLoader().load_file(tmp_path)

    @pytest.mark.skipif(
        os.name == "nt" or os.geteuid() == 0, reason="permission bits not enforced"
    )
    def test_permission_denied_on_stat_or_open(self, write_json):
        path = write_json(ARRAY_DECK)
        path.chmod(0)
        try:
            with pytest.raises(FileAccessError, match="Permission denied"):
                FlashcardLoader().load_file(path)
        finally:
            path.chmod(0o600)

    def test_other_os_error_on_stat(self, monkeypatch, tmp_path: Path):
        def boom(self):
            raise OSError(5, "Input/output error")

        monkeypatch.setattr(Path, "stat", boom)
        with pytest.raises(FileAccessError, match="Input/output error"):
            FlashcardLoader().load_file(tmp_path / "x.json")

    def test_other_os_error_on_open(self, monkeypatch, write_json):
        path = write_json(ARRAY_DECK)

        def boom(self, *args, **kwargs):
            raise OSError(5, "Input/output error")

        monkeypatch.setattr(Path, "open", boom)
        with pytest.raises(FileAccessError, match="Could not read"):
            FlashcardLoader().load_file(path)

    def test_permission_error_on_open(self, monkeypatch, write_json):
        path = write_json(ARRAY_DECK)

        def boom(self, *args, **kwargs):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(Path, "open", boom)
        with pytest.raises(FileAccessError, match="Permission denied"):
            FlashcardLoader().load_file(path)

    def test_invalid_utf8_file(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_bytes(b'[{"front": "\xff\xfe", "back": "A"}]')
        with pytest.raises(MalformedJSONError, match="not valid utf-8"):
            FlashcardLoader().load_file(path)

    def test_file_too_large_detected_before_reading(self, write_json):
        path = write_json(ARRAY_DECK)
        loader = FlashcardLoader(LoaderConfig(max_file_bytes=10))
        with pytest.raises(FileTooLargeError, match="limit is 10 bytes"):
            loader.load_file(path)

    def test_string_too_large(self):
        loader = FlashcardLoader(LoaderConfig(max_file_bytes=5))
        with pytest.raises(FileTooLargeError):
            loader.load_string("[" + " " * 10 + "]")

    def test_too_many_cards(self):
        loader = FlashcardLoader(LoaderConfig(max_cards=1))
        with pytest.raises(DeckTooLargeError, match="has 2 cards; the limit is 1"):
            loader.load_data(ARRAY_DECK)

    def test_empty_deck_rejected_by_default(self):
        with pytest.raises(EmptyDeckError, match="contains no cards"):
            FlashcardLoader().load_data([])

    def test_empty_deck_allowed_when_configured(self):
        deck = FlashcardLoader(LoaderConfig(allow_empty=True)).load_data({"cards": []})
        assert len(deck) == 0 and deck.format_name == "object"

    def test_all_cards_skipped_is_empty_deck_error(self):
        loader = FlashcardLoader(LoaderConfig(on_invalid_card="skip"))
        with pytest.raises(EmptyDeckError, match="All 2 cards were skipped"):
            loader.load_data([{"front": "Q"}, {"back": "A"}])


# --------------------------------------------------------------------------- #
# Skip / dedupe behaviour and events
# --------------------------------------------------------------------------- #


class TestSkipAndDedupe:
    def test_skip_mode_drops_invalid_and_emits_events(self):
        loader = FlashcardLoader(LoaderConfig(on_invalid_card="skip"))
        collector = CollectingObserver()
        loader.events.subscribe(collector)
        deck = loader.load_data(
            [{"front": "Q1", "back": "A1"}, "junk", {"front": "Q2"}], source="s"
        )
        assert len(deck) == 1 and deck.skipped == 2
        skipped = collector.of_kind(EventKind.CARD_SKIPPED)
        assert [e.index for e in skipped] == [1, 2]
        assert all(e.source == "s" for e in skipped)

    def test_dedupe_removes_exact_repeats_and_counts(self):
        loader = FlashcardLoader()
        collector = CollectingObserver()
        loader.events.subscribe(collector)
        deck = loader.load_data(
            [{"front": "Q", "back": "A"}, {"front": " Q ", "back": "A", "hint": "x"}]
        )
        assert len(deck) == 1 and deck.duplicates_removed == 1
        assert len(collector.of_kind(EventKind.DUPLICATE_REMOVED)) == 1

    def test_dedupe_can_be_disabled(self):
        loader = FlashcardLoader(LoaderConfig(dedupe=False))
        deck = loader.load_data([{"front": "Q", "back": "A"}] * 3)
        assert len(deck) == 3 and deck.duplicates_removed == 0

    def test_lifecycle_events_are_published(self):
        loader = FlashcardLoader()
        collector = CollectingObserver()
        loader.events.subscribe(collector)
        loader.load_data(OBJECT_DECK, source="mem")
        kinds = [e.kind for e in collector.events]
        assert kinds == [EventKind.FORMAT_DETECTED, EventKind.DECK_LOADED]
        assert "object" in collector.events[0].message
        assert "Loaded 2 card(s)" in collector.events[1].message

    def test_sample_with_mixed_problems(self, samples_dir: Path):
        loader = FlashcardLoader(LoaderConfig(on_invalid_card="skip"))
        deck = loader.load_file(samples_dir / "invalid_missing_fields.json")
        assert (len(deck), deck.skipped, deck.duplicates_removed) == (2, 2, 1)


# --------------------------------------------------------------------------- #
# Caching
# --------------------------------------------------------------------------- #


class TestCaching:
    def test_second_load_of_unchanged_file_hits_cache(self, write_json):
        path = write_json(ARRAY_DECK)
        loader = FlashcardLoader()
        collector = CollectingObserver()
        loader.events.subscribe(collector)
        first = loader.load_file(path)
        second = loader.load_file(path)
        assert first is second
        assert loader.cache_size == 1
        assert len(collector.of_kind(EventKind.CACHE_HIT)) == 1

    def test_modified_file_is_reparsed(self, write_json):
        path = write_json(ARRAY_DECK)
        loader = FlashcardLoader()
        first = loader.load_file(path)
        path.write_text(
            json.dumps([{"front": "new", "back": "card"}]), encoding="utf-8"
        )
        # Force a distinct mtime even on coarse filesystems.
        stamp = path.stat()
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000))
        second = loader.load_file(path)
        assert second is not first and second[0].front == "new"

    def test_cache_disabled_with_zero_size(self, write_json):
        path = write_json(ARRAY_DECK)
        loader = FlashcardLoader(LoaderConfig(cache_size=0))
        a = loader.load_file(path)
        b = loader.load_file(path)
        assert a is not b and a == b and loader.cache_size == 0

    def test_cache_is_bounded(self, tmp_path: Path):
        loader = FlashcardLoader(LoaderConfig(cache_size=2))
        for i in range(5):
            path = tmp_path / f"d{i}.json"
            path.write_text(
                json.dumps([{"front": str(i), "back": "x"}]), encoding="utf-8"
            )
            loader.load_file(path)
        assert loader.cache_size == 2

    def test_clear_cache(self, write_json):
        path = write_json(ARRAY_DECK)
        loader = FlashcardLoader()
        loader.load_file(path)
        loader.clear_cache()
        assert loader.cache_size == 0


# --------------------------------------------------------------------------- #
# Other entry points
# --------------------------------------------------------------------------- #


class TestEntryPoints:
    def test_load_stream(self):
        stream = io.StringIO(json.dumps(ARRAY_DECK))
        deck = FlashcardLoader().load_stream(stream, source="stdin")
        assert len(deck) == 2 and deck.source == "stdin"

    def test_load_stream_respects_size_limit(self):
        loader = FlashcardLoader(LoaderConfig(max_file_bytes=4))
        with pytest.raises(FileTooLargeError):
            loader.load_stream(io.StringIO("[" + " " * 20 + "]"))

    def test_load_dispatches_path(self, write_json):
        path = write_json(OBJECT_DECK)
        assert FlashcardLoader().load(str(path)).title == "Demo"
        assert FlashcardLoader().load(path).title == "Demo"

    def test_load_dispatches_url_to_fetcher(self, monkeypatch):
        calls = {}

        def fake_fetch(url, **kwargs):
            calls.update(url=url, **kwargs)
            return json.dumps(ARRAY_DECK)

        monkeypatch.setattr("flashcards.remote.fetch_text", fake_fetch)
        loader = FlashcardLoader(LoaderConfig(request_timeout=3.0, max_file_bytes=999))
        deck = loader.load("HTTPS://example.com/deck.json")
        assert deck.source == "HTTPS://example.com/deck.json"
        assert calls["timeout"] == 3.0 and calls["max_bytes"] == 999
        assert calls["encoding"] == "utf-8"

    def test_load_url_with_injected_fetcher(self):
        deck = FlashcardLoader().load_url(
            "http://x/y", fetcher=lambda url, **kw: json.dumps(OBJECT_DECK)
        )
        assert deck.title == "Demo"

    def test_config_property(self):
        config = LoaderConfig(max_cards=3)
        assert FlashcardLoader(config).config is config

    def test_default_config_when_none(self):
        assert FlashcardLoader().config == LoaderConfig()

    @pytest.mark.skipif(sys.platform == "win32", reason="posix path semantics")
    def test_cache_key_uses_resolved_path(self, write_json, tmp_path: Path):
        path = write_json(ARRAY_DECK)
        loader = FlashcardLoader()
        a = loader.load_file(path)
        b = loader.load_file(tmp_path / "." / path.name)
        assert a is b


# --------------------------------------------------------------------------- #
# Boundary conditions and configuration propagation
# (added after mutation testing showed these were unverified)
# --------------------------------------------------------------------------- #


class TestBoundariesAndPropagation:
    def test_validator_receives_loader_config(self):
        loader = FlashcardLoader(LoaderConfig(max_field_length=3))
        with pytest.raises(InvalidCardError, match="too long"):
            loader.load_data([{"front": "abcd", "back": "A"}])

    def test_file_encoding_from_config_is_used(self, tmp_path: Path):
        path = tmp_path / "latin.json"
        path.write_bytes('[{"front": "caf\u00e9", "back": "A"}]'.encode("latin-1"))
        with pytest.raises(MalformedJSONError, match="not valid utf-8"):
            FlashcardLoader().load_file(path)
        deck = FlashcardLoader(LoaderConfig(encoding="latin-1")).load_file(path)
        assert deck[0].front == "caf\u00e9"

    def test_file_exactly_at_size_limit_loads(self, tmp_path: Path):
        text = json.dumps([{"front": "Q", "back": "A"}])
        path = tmp_path / "exact.json"
        path.write_text(text, encoding="utf-8")
        size = path.stat().st_size
        assert (
            len(FlashcardLoader(LoaderConfig(max_file_bytes=size)).load_file(path)) == 1
        )
        with pytest.raises(FileTooLargeError):
            FlashcardLoader(LoaderConfig(max_file_bytes=size - 1)).load_file(path)

    def test_string_exactly_at_size_limit_loads(self):
        text = json.dumps([{"front": "Q", "back": "A"}])
        assert (
            len(
                FlashcardLoader(LoaderConfig(max_file_bytes=len(text))).load_string(
                    text
                )
            )
            == 1
        )

    def test_string_size_limit_counts_utf8_bytes(self):
        text = json.dumps([{"front": "\u00e9", "back": "A"}], ensure_ascii=False)
        byte_size = len(text.encode("utf-8"))
        assert (
            len(
                FlashcardLoader(LoaderConfig(max_file_bytes=byte_size)).load_string(
                    text
                )
            )
            == 1
        )

        with pytest.raises(FileTooLargeError):
            FlashcardLoader(LoaderConfig(max_file_bytes=byte_size - 1)).load_string(
                text
            )

    def test_stream_exactly_at_size_limit_loads(self):
        text = json.dumps([{"front": "Q", "back": "A"}])
        loader = FlashcardLoader(LoaderConfig(max_file_bytes=len(text)))
        assert len(loader.load_stream(io.StringIO(text))) == 1

    def test_stream_size_limit_counts_utf8_bytes(self):
        text = json.dumps([{"front": "\u00e9", "back": "A"}], ensure_ascii=False)
        byte_size = len(text.encode("utf-8"))
        assert (
            len(
                FlashcardLoader(LoaderConfig(max_file_bytes=byte_size)).load_stream(
                    io.StringIO(text)
                )
            )
            == 1
        )

        with pytest.raises(FileTooLargeError):
            FlashcardLoader(LoaderConfig(max_file_bytes=byte_size - 1)).load_stream(
                io.StringIO(text)
            )

    def test_deck_exactly_at_card_limit_loads(self):
        loader = FlashcardLoader(LoaderConfig(max_cards=2))
        assert len(loader.load_data(ARRAY_DECK)) == 2

    def test_multiple_duplicates_are_all_counted(self):
        deck = FlashcardLoader().load_data([{"front": "Q", "back": "A"}] * 4)
        assert len(deck) == 1 and deck.duplicates_removed == 3

    def test_error_and_event_metadata_carry_source_and_index(self, write_json):
        path = write_json(ARRAY_DECK)
        loader = FlashcardLoader(LoaderConfig(on_invalid_card="skip"))
        collector = CollectingObserver()
        loader.events.subscribe(collector)

        loader.load_file(path)
        loader.load_file(path)
        hit = collector.of_kind(EventKind.CACHE_HIT)[0]
        assert hit.source == str(path) and hit.index is None

        collector.clear()
        loader.load_data(
            [{"front": "Q", "back": "A"}, {"front": "Q", "back": "A"}, {"back": "x"}],
            source="mem",
        )
        dup = collector.of_kind(EventKind.DUPLICATE_REMOVED)[0]
        skipped = collector.of_kind(EventKind.CARD_SKIPPED)[0]
        assert (dup.source, dup.index) == ("mem", 1)
        assert (skipped.source, skipped.index) == ("mem", 2)
        loaded = collector.of_kind(EventKind.DECK_LOADED)[0]
        assert loaded.source == "mem"

        with pytest.raises(FileTooLargeError) as big:
            FlashcardLoader(LoaderConfig(max_file_bytes=1)).load_string(
                "[]", source="s1"
            )
        assert big.value.source == "s1"
        with pytest.raises(MalformedJSONError) as empty:
            FlashcardLoader().load_string("  ", source="s2")
        assert empty.value.source == "s2"
        with pytest.raises(FileAccessError) as direct:
            FlashcardLoader().load_file(path.parent)
        assert "inside it" in direct.value.hint

    def test_default_sources(self):
        loader = FlashcardLoader(LoaderConfig(allow_empty=True))
        assert loader.load_string("[]").source == "<string>"
        assert loader.load_data([]).source == "<data>"
        assert loader.load_stream(io.StringIO("[]")).source == "<stream>"

    def test_injected_fetcher_is_used_and_default_is_not(self, monkeypatch):
        def never(*args, **kwargs):
            raise AssertionError("default fetch_text must not be called")

        monkeypatch.setattr("flashcards.remote.fetch_text", never)
        calls = []

        def fake(url, **kwargs):
            calls.append(url)
            return json.dumps(ARRAY_DECK)

        deck = FlashcardLoader().load_url("https://h/x", fetcher=fake)
        assert calls == ["https://h/x"] and len(deck) == 2


class TestCacheKeyIdentity:
    def test_identical_files_with_same_size_and_mtime_are_not_confused(
        self, tmp_path: Path
    ):
        """The cache key must include the path, not just size + mtime."""
        text = json.dumps([{"front": "Q", "back": "A"}])
        first = tmp_path / "first.json"
        second = tmp_path / "second.json"
        first.write_text(text, encoding="utf-8")
        second.write_text(text, encoding="utf-8")
        stamp = first.stat()
        os.utime(second, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        assert first.stat().st_mtime_ns == second.stat().st_mtime_ns

        loader = FlashcardLoader()
        assert loader.load_file(first).source == str(first)
        assert loader.load_file(second).source == str(second)
        assert loader.cache_size == 2

    def test_cache_hit_event_message_names_the_file(self, write_json):
        path = write_json(ARRAY_DECK)
        loader = FlashcardLoader()
        collector = CollectingObserver()
        loader.events.subscribe(collector)
        loader.load_file(path)
        loader.load_file(path)
        assert str(path) in collector.of_kind(EventKind.CACHE_HIT)[0].message

    def test_file_too_large_error_names_the_file(self, write_json):
        path = write_json(ARRAY_DECK)
        with pytest.raises(FileTooLargeError) as info:
            FlashcardLoader(LoaderConfig(max_file_bytes=1)).load_file(path)
        assert info.value.source == str(path)

    def test_invalid_utf8_error_keeps_specific_hint_and_source(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_bytes(b"\xff")
        with pytest.raises(MalformedJSONError) as info:
            FlashcardLoader().load_file(path)
        assert info.value.source == str(path)
        assert "Save the file as UTF-8" in info.value.hint
