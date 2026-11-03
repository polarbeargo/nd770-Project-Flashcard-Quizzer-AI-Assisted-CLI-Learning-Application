"""Tests for logging configuration (idempotency, no handler leaks)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from flashcards.logging_config import (
    LOGGER_NAME,
    configure_logging,
    get_logger,
    reset_logging,
)


def managed_handlers() -> list[logging.Handler]:
    return [
        h
        for h in logging.getLogger(LOGGER_NAME).handlers
        if getattr(h, "_flashcards_managed", False)
    ]


def test_get_logger_names():
    assert get_logger().name == LOGGER_NAME
    assert get_logger("cli").name == f"{LOGGER_NAME}.cli"


def test_package_import_installs_null_handler():
    import flashcards  # noqa: F401

    assert any(isinstance(h, logging.NullHandler) for h in get_logger().handlers)


def test_configure_stream_only_by_default(capsys):
    logger = configure_logging("WARNING")
    assert len(managed_handlers()) == 1
    assert logger.level == logging.WARNING
    assert logger.propagate is False
    logger.warning("hello")
    assert "hello" in capsys.readouterr().err


def test_configure_file_only(tmp_path: Path):
    log_file = tmp_path / "app.log"
    logger = configure_logging(logging.INFO, log_file=log_file)
    handlers = managed_handlers()
    assert len(handlers) == 1 and isinstance(handlers[0], logging.FileHandler)
    logger.info("to file")
    reset_logging()
    assert "to file" in log_file.read_text(encoding="utf-8")


def test_configure_file_and_stream(tmp_path: Path):
    import io

    stream = io.StringIO()
    configure_logging("DEBUG", log_file=tmp_path / "a.log", stream=stream)
    assert len(managed_handlers()) == 2
    get_logger().debug("both")
    assert "both" in stream.getvalue()


def test_repeated_configure_does_not_accumulate_handlers():
    for _ in range(5):
        configure_logging("INFO")
    assert len(managed_handlers()) == 1


def test_reset_closes_and_removes():
    configure_logging("INFO")
    reset_logging()
    assert managed_handlers() == []


def test_unknown_level_name_rejected():
    with pytest.raises(ValueError, match="Unknown log level"):
        configure_logging("LOUD")


def test_capacity_one_cache_stores_one_item():
    from flashcards.loader import LRUCache

    cache: LRUCache[str, int] = LRUCache(1)
    cache.put("a", 1)
    assert cache.get("a") == 1 and len(cache) == 1
    cache.put("b", 2)
    assert cache.get("a") is None and cache.get("b") == 2
