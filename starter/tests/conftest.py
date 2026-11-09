"""Shared fixtures for the flashcard test suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from flashcards.logging_config import reset_logging

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"

ARRAY_DECK = [
    {"front": "Q1", "back": "A1"},
    {"front": "Q2", "back": "A2", "hint": "h", "tags": ["t1", "t2"]},
]
OBJECT_DECK = {"title": "Demo", "cards": ARRAY_DECK}


@pytest.fixture
def write_json(tmp_path: Path) -> Callable[[Any, str], Path]:
    """Write ``data`` as JSON (or raw text) into a temp file and return the path."""

    def _write(data: Any, name: str = "deck.json") -> Path:
        target = tmp_path / name
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        target.write_text(text, encoding="utf-8")
        return target

    return _write


@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES


@pytest.fixture(autouse=True)
def _clean_logging():
    """Guarantee no handler leakage between tests."""
    yield
    reset_logging()
