"""
Concurrency and resource-leak tests.

These exercise the loader, event bus, exporter factory and cache from many
threads at once and assert that results are correct, nothing deadlocks, and
no objects or handlers are leaked.
"""

from __future__ import annotations

import gc
import json
import threading
import tracemalloc
import weakref
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from flashcards import (
    CollectingObserver,
    EventBus,
    EventKind,
    FlashcardLoader,
    LoaderConfig,
    export_deck,
)
from flashcards.events import LoadEvent
from flashcards.exporters import Exporter, ExporterFactory
from flashcards.loader import LRUCache
from flashcards.logging_config import LOGGER_NAME, configure_logging, reset_logging

THREADS = 16
ITERATIONS = 25


def _write_deck(path: Path, size: int) -> Path:
    cards = [{"front": f"Q{i}", "back": f"A{i}", "tags": ["t"]} for i in range(size)]
    path.write_text(json.dumps(cards), encoding="utf-8")
    return path


class TestConcurrentLoading:
    def test_shared_loader_many_threads_same_file(self, tmp_path: Path):
        path = _write_deck(tmp_path / "deck.json", 200)
        loader = FlashcardLoader()
        collector = CollectingObserver()
        loader.events.subscribe(collector)

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            decks = list(pool.map(lambda _: loader.load_file(path), range(THREADS * 4)))

        assert all(len(deck) == 200 for deck in decks)
        # Every thread must see identical, correctly ordered content.
        assert all(deck.cards == decks[0].cards for deck in decks)
        assert decks[0][199].front == "Q199"
        loaded = collector.of_kind(EventKind.DECK_LOADED)
        hits = collector.of_kind(EventKind.CACHE_HIT)
        # Every call either parsed or hit the cache; nothing was lost, and
        # at least one call must have been served from the cache.
        assert len(loaded) + len(hits) == THREADS * 4
        assert len(hits) >= 1
        assert loader.cache_size == 1

    def test_many_distinct_files_respect_cache_bound(self, tmp_path: Path):
        paths = [_write_deck(tmp_path / f"d{i}.json", 5) for i in range(40)]
        loader = FlashcardLoader(LoaderConfig(cache_size=4))

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            results = list(pool.map(loader.load_file, paths * 3))

        # Each result must correspond to the file that was requested - a
        # cache keyed incorrectly would hand back another file's deck.
        for path, deck in zip(paths * 3, results):
            assert deck.source == str(path)
            assert len(deck) == 5 and deck[0].front == "Q0"
        assert loader.cache_size == 4

    def test_skip_mode_counts_are_exact_under_concurrency(self):
        data = [
            {"front": "Q", "back": "A"},
            {"front": "bad"},
            {"front": "Q", "back": "A"},
        ]
        loader = FlashcardLoader(LoaderConfig(on_invalid_card="skip"))
        collector = CollectingObserver()
        loader.events.subscribe(collector)

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            decks = list(
                pool.map(lambda _: loader.load_data(data), range(ITERATIONS * 4))
            )

        assert all(
            (len(d), d.skipped, d.duplicates_removed) == (1, 1, 1) for d in decks
        )
        assert len(collector.of_kind(EventKind.CARD_SKIPPED)) == ITERATIONS * 4
        assert len(collector.of_kind(EventKind.DUPLICATE_REMOVED)) == ITERATIONS * 4


class TestEventBusConcurrency:
    def test_concurrent_subscribe_publish_unsubscribe(self):
        bus = EventBus()
        received = []
        lock = threading.Lock()
        barrier = threading.Barrier(THREADS)

        def worker(n: int) -> None:
            def observer(event: LoadEvent) -> None:
                with lock:
                    received.append((n, event.message))

            barrier.wait()
            for i in range(ITERATIONS):
                sub = bus.subscribe(observer)
                bus.publish(LoadEvent(EventKind.DECK_LOADED, f"{n}:{i}"))
                sub.unsubscribe()

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            list(pool.map(worker, range(THREADS)))

        assert len(bus) == 0
        # Each observer received at least its own publish while subscribed.
        own = {(n, f"{n}:{i}") for n in range(THREADS) for i in range(ITERATIONS)}
        assert own.issubset(set(received))


class TestLRUCacheConcurrency:
    def test_bounded_under_hammering(self):
        cache: LRUCache[int, int] = LRUCache(8)

        def worker(n: int) -> None:
            for i in range(500):
                key = (n * 500 + i) % 64
                cache.put(key, i)
                cache.get(key)

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            list(pool.map(worker, range(THREADS)))

        assert len(cache) == 8


class TestExporterFactoryConcurrency:
    def test_concurrent_registration(self):
        factory = ExporterFactory(include_defaults=False)

        def register(n: int) -> None:
            cls = type(
                f"Exp{n}",
                (Exporter,),
                {
                    "name": f"fmt{n}",
                    "extension": f".e{n}",
                    "render": lambda self, d: "",
                },
            )
            factory.register(cls)

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            list(pool.map(register, range(64)))

        assert len(factory.available()) == 64

    def test_concurrent_atomic_exports_to_distinct_files(self, tmp_path: Path):
        deck = FlashcardLoader().load_data([{"front": "Q", "back": "A"}])

        def do_export(n: int) -> Path:
            return export_deck(deck, tmp_path / f"out{n}.json")

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            paths = list(pool.map(do_export, range(THREADS * 2)))

        assert all(p.exists() for p in paths)
        leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".tmp-")]
        assert leftovers == []


class TestNoLeaks:
    def test_loader_and_decks_are_collectable(self, tmp_path: Path):
        path = _write_deck(tmp_path / "deck.json", 50)
        loader = FlashcardLoader()
        deck = loader.load_file(path)
        loader_ref = weakref.ref(loader)
        # Deck is slotted (no __weakref__), so track it through a referrer
        # count instead: only the local name and the loader cache hold it.
        assert len(gc.get_referrers(deck)) <= 2
        del loader, deck
        gc.collect()
        assert loader_ref() is None

    def test_observer_released_after_unsubscribe_in_cli_style_usage(self):
        loader = FlashcardLoader()
        collector = CollectingObserver()
        ref = weakref.ref(collector)
        with loader.events.subscribe(collector):
            loader.load_data([{"front": "Q", "back": "A"}])
        del collector
        gc.collect()
        assert ref() is None

    def test_repeated_logging_configuration_has_no_handler_growth(self):
        import logging

        base = len(logging.getLogger(LOGGER_NAME).handlers)
        for _ in range(20):
            configure_logging("INFO")
        assert len(logging.getLogger(LOGGER_NAME).handlers) == base + 1
        reset_logging()
        assert len(logging.getLogger(LOGGER_NAME).handlers) == base

    @pytest.mark.slow
    def test_repeated_loads_do_not_grow_memory(self):
        """Steady-state memory after warm-up should stay flat."""
        data = [{"front": f"Q{i}", "back": f"A{i}"} for i in range(300)]
        text = json.dumps(data)
        loader = FlashcardLoader(LoaderConfig(cache_size=0))

        for _ in range(20):  # warm up allocator / caches
            loader.load_string(text)
        gc.collect()
        tracemalloc.start()
        try:
            before = tracemalloc.take_snapshot()
            for _ in range(200):
                loader.load_string(text)
            gc.collect()
            after = tracemalloc.take_snapshot()
        finally:
            tracemalloc.stop()

        growth = sum(stat.size_diff for stat in after.compare_to(before, "filename"))
        # Allow a small tolerance for interpreter-internal noise (< 64 KiB).
        assert growth < 64 * 1024, f"memory grew by {growth} bytes"
