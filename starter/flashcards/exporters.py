"""
Factory pattern: pluggable deck exporters.

``ExporterFactory`` maps a format name (``json``, ``csv``, ``markdown``) to an
:class:`Exporter` implementation. New formats register themselves without
touching the CLI or loader. :func:`export_deck` writes atomically (temp file +
``os.replace``) so a crash mid-write can never leave a half-written deck, and
the temp file is always cleaned up.
"""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Tuple, Type, Union

from .exceptions import ExportError
from .models import Deck

PathLike = Union[str, "os.PathLike[str]"]


class Exporter(ABC):
    """Base class for deck serialisers."""

    name: str = ""
    extension: str = ""

    @abstractmethod
    def render(self, deck: Deck) -> str:
        """Return the deck serialised as text."""


class JsonExporter(Exporter):
    """Canonical object-format JSON (round-trips through the loader)."""

    name = "json"
    extension = ".json"

    def render(self, deck: Deck) -> str:
        return json.dumps(deck.to_dict(), indent=2, ensure_ascii=False) + "\n"


class CsvExporter(Exporter):
    """RFC 4180 CSV with spreadsheet formula-injection protection."""

    name = "csv"
    extension = ".csv"
    _FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

    def render(self, deck: Deck) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(["front", "back", "hint", "tags"])
        for card in deck.cards:
            writer.writerow(
                [
                    self._neutralise(card.front),
                    self._neutralise(card.back),
                    self._neutralise(card.hint or ""),
                    self._neutralise(";".join(card.tags)),
                ]
            )
        return buffer.getvalue()

    @classmethod
    def _neutralise(cls, text: str) -> str:
        """Prefix cells that spreadsheets would evaluate as formulas."""
        if text.startswith(cls._FORMULA_PREFIXES):
            return "'" + text
        return text


class MarkdownExporter(Exporter):
    """A GitHub-flavoured Markdown table."""

    name = "markdown"
    extension = ".md"

    def render(self, deck: Deck) -> str:
        lines = [f"# {deck.title or 'Flashcards'}", ""]
        lines.append("| # | Front | Back | Hint | Tags |")
        lines.append("|---|-------|------|------|------|")
        for number, card in enumerate(deck.cards, start=1):
            lines.append(
                f"| {number} | {self._cell(card.front)} | {self._cell(card.back)} | "
                f"{self._cell(card.hint or '')} | {self._cell(', '.join(card.tags))} |"
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _cell(text: str) -> str:
        return text.replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")


class ExporterFactory:
    """Thread-safe registry that creates exporters by name or file extension."""

    def __init__(self, include_defaults: bool = True) -> None:
        self._lock = threading.Lock()
        self._by_name: Dict[str, Type[Exporter]] = {}
        self._by_extension: Dict[str, Type[Exporter]] = {}
        if include_defaults:
            for cls in (JsonExporter, CsvExporter, MarkdownExporter):
                self.register(cls)

    def register(self, exporter_cls: Type[Exporter]) -> Type[Exporter]:
        """Register an exporter class; usable as a decorator."""
        if not (isinstance(exporter_cls, type) and issubclass(exporter_cls, Exporter)):
            raise TypeError("exporter_cls must be a subclass of Exporter")
        if not exporter_cls.name or not exporter_cls.extension:
            raise ValueError("Exporter subclasses must define 'name' and 'extension'")
        with self._lock:
            self._by_name[exporter_cls.name.lower()] = exporter_cls
            self._by_extension[exporter_cls.extension.lower()] = exporter_cls
        return exporter_cls

    def available(self) -> Tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._by_name))

    def create(self, name: str) -> Exporter:
        with self._lock:
            exporter_cls = self._by_name.get(name.lower())
        if exporter_cls is None:
            raise ExportError(
                f"Unknown export format {name!r}.",
                hint=f"Available formats: {', '.join(self.available())}.",
            )
        return exporter_cls()

    def for_path(self, path: PathLike) -> Exporter:
        suffix = Path(path).suffix.lower()
        with self._lock:
            exporter_cls = self._by_extension.get(suffix)
        if exporter_cls is None:
            raise ExportError(
                f"Cannot infer an export format from the extension "
                f"{suffix or '(none)'!r}.",
                hint="Pass --format explicitly, e.g. --format csv.",
            )
        return exporter_cls()


DEFAULT_FACTORY = ExporterFactory()


def export_deck(
    deck: Deck,
    path: PathLike,
    *,
    fmt: Optional[str] = None,
    factory: Optional[ExporterFactory] = None,
    encoding: str = "utf-8",
) -> Path:
    """Render ``deck`` and write it atomically to ``path``; returns the path."""
    registry = factory or DEFAULT_FACTORY
    exporter = registry.create(fmt) if fmt else registry.for_path(path)
    target = Path(path)
    content = exporter.render(deck)

    if target.is_dir():
        raise ExportError(f"{str(target)!r} is a directory.")
    temp_name: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding=encoding, dir=target.parent, prefix=".tmp-", delete=False
        ) as handle:
            temp_name = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
        temp_name = None
    except OSError as exc:
        raise ExportError(
            f"Could not write {str(target)!r}: {exc.strerror or exc}."
        ) from None
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
    return target
