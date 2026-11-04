"""Tests for the EventBus observer implementation."""

from __future__ import annotations

import gc
import logging
import weakref

import pytest

from flashcards.events import (
    CollectingObserver,
    EventBus,
    EventKind,
    LoadEvent,
    Subscription,
    log_event,
)


def make_event(kind: EventKind = EventKind.DECK_LOADED, msg: str = "m") -> LoadEvent:
    return LoadEvent(kind, msg, source="s", index=None)


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        collector = CollectingObserver()
        bus.subscribe(collector)
        bus.publish(make_event())
        assert len(collector.events) == 1
        assert collector.events[0].kind is EventKind.DECK_LOADED

    def test_publish_without_observers_is_noop(self):
        EventBus().publish(make_event())  # must not raise

    def test_non_callable_rejected(self):
        with pytest.raises(TypeError):
            EventBus().subscribe("nope")  # type: ignore[arg-type]

    def test_unsubscribe_stops_delivery_and_is_idempotent(self):
        bus = EventBus()
        collector = CollectingObserver()
        sub = bus.subscribe(collector)
        assert len(bus) == 1 and sub.active
        sub.unsubscribe()
        sub.unsubscribe()
        assert len(bus) == 0 and not sub.active
        bus.publish(make_event())
        assert collector.events == []

    def test_subscription_context_manager(self):
        bus = EventBus()
        with bus.subscribe(CollectingObserver()) as sub:
            assert isinstance(sub, Subscription)
            assert len(bus) == 1
        assert len(bus) == 0

    def test_clear_removes_everything(self):
        bus = EventBus()
        bus.subscribe(lambda e: None)
        bus.subscribe(lambda e: None)
        bus.clear()
        assert len(bus) == 0

    def test_faulty_observer_is_isolated_and_logged(self, caplog):
        bus = EventBus()
        good = CollectingObserver()

        def bad(event: LoadEvent) -> None:
            raise RuntimeError("boom")

        bus.subscribe(bad)
        bus.subscribe(good)
        with caplog.at_level(logging.ERROR, logger="flashcards.events"):
            bus.publish(make_event())
        assert len(good.events) == 1
        assert "Observer" in caplog.text and "boom" in caplog.text

    def test_observer_may_unsubscribe_during_callback(self):
        bus = EventBus()
        seen = []
        holder = {}

        def once(event: LoadEvent) -> None:
            seen.append(event)
            holder["sub"].unsubscribe()

        holder["sub"] = bus.subscribe(once)
        bus.publish(make_event())
        bus.publish(make_event())
        assert len(seen) == 1

    def test_unsubscribed_observer_is_garbage_collected(self):
        """Regression guard against the classic observer-list memory leak."""
        bus = EventBus()
        collector = CollectingObserver()
        ref = weakref.ref(collector)
        sub = bus.subscribe(collector)
        del collector
        gc.collect()
        assert ref() is not None  # bus still holds it while subscribed
        sub.unsubscribe()
        gc.collect()
        assert ref() is None


class TestCollectingObserver:
    def test_of_kind_and_clear(self):
        collector = CollectingObserver()
        collector(make_event(EventKind.CARD_SKIPPED))
        collector(make_event(EventKind.DECK_LOADED))
        assert len(collector.of_kind(EventKind.CARD_SKIPPED)) == 1
        collector.clear()
        assert collector.events == []

    def test_events_returns_copy(self):
        collector = CollectingObserver()
        collector(make_event())
        collector.events.clear()
        assert len(collector.events) == 1


class TestLogEvent:
    @pytest.mark.parametrize(
        "kind, level",
        [
            (EventKind.FORMAT_DETECTED, logging.DEBUG),
            (EventKind.CACHE_HIT, logging.DEBUG),
            (EventKind.DECK_LOADED, logging.INFO),
            (EventKind.DUPLICATE_REMOVED, logging.INFO),
            (EventKind.CARD_SKIPPED, logging.WARNING),
        ],
    )
    def test_maps_kind_to_level(self, caplog, kind, level):
        with caplog.at_level(logging.DEBUG, logger="flashcards.events"):
            log_event(make_event(kind, "hello"))
        record = caplog.records[-1]
        assert record.levelno == level and record.getMessage() == "hello"


class TestEdgeCases:
    def test_unsubscribe_after_clear_is_safe(self):
        bus = EventBus()
        sub = bus.subscribe(lambda e: None)
        bus.clear()
        sub.unsubscribe()  # token already gone; must not raise
        assert sub.active is False

    def test_active_is_strictly_boolean(self):
        bus = EventBus()
        sub = bus.subscribe(lambda e: None)
        assert sub.active is True
        sub.unsubscribe()
        assert sub.active is False

    def test_faulty_observer_log_names_the_event_kind(self, caplog):
        bus = EventBus()
        bus.subscribe(lambda e: 1 / 0)
        with caplog.at_level(logging.ERROR, logger="flashcards.events"):
            bus.publish(make_event(EventKind.CARD_SKIPPED))
        assert "card_skipped" in caplog.text.lower()

    def test_log_event_is_safe_with_percent_in_message(self, caplog):
        with caplog.at_level(logging.INFO, logger="flashcards.events"):
            log_event(make_event(EventKind.DECK_LOADED, "100% done %s %d"))
        assert caplog.records[-1].getMessage() == "100% done %s %d"
