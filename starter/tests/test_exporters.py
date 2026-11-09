"""Tests for exporters, the exporter factory and atomic file writing."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

import pytest

from flashcards.exceptions import ExportError
from flashcards.exporters import (
    CsvExporter,
    Exporter,
    ExporterFactory,
    JsonExporter,
    MarkdownExporter,
    export_deck,
)
from flashcards.models import Deck, Flashcard


@pytest.fixture
def deck() -> Deck:
    return Deck(
        cards=(
            Flashcard("What is 2+2?", "4", tags=("math", "easy")),
            Flashcard("=SUM(A1)", "-1", hint="a|b\nc"),
        ),
        title="Sample",
    )


class TestJsonExporter:
    def test_round_trips_object_format(self, deck: Deck):
        data = json.loads(JsonExporter().render(deck))
        assert data["title"] == "Sample"
        assert data["cards"][0]["tags"] == ["math", "easy"]
        assert "hint" not in data["cards"][0]

    def test_keeps_unicode(self):
        deck = Deck(cards=(Flashcard("日本", "語"),))
        assert "日本" in JsonExporter().render(deck)


class TestCsvExporter:
    def test_header_and_rows(self, deck: Deck):
        rows = list(csv.reader(io.StringIO(CsvExporter().render(deck))))
        assert rows[0] == ["front", "back", "hint", "tags"]
        assert rows[1] == ["What is 2+2?", "4", "", "math;easy"]

    def test_formula_injection_neutralised(self, deck: Deck):
        rows = list(csv.reader(io.StringIO(CsvExporter().render(deck))))
        assert rows[2][0] == "'=SUM(A1)"
        assert rows[2][1] == "'-1"

    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
    def test_all_dangerous_prefixes(self, prefix):
        assert CsvExporter._neutralise(prefix + "x").startswith("'")

    def test_safe_text_untouched(self):
        assert CsvExporter._neutralise("hello") == "hello"


class TestMarkdownExporter:
    def test_table_structure_and_escaping(self, deck: Deck):
        text = MarkdownExporter().render(deck)
        lines = text.splitlines()
        assert lines[0] == "# Sample"
        assert lines[2].startswith("| # | Front |")
        assert "a\\|b<br>c" in lines[5]

    def test_default_title(self):
        text = MarkdownExporter().render(Deck(cards=()))
        assert text.startswith("# Flashcards")

    def test_crlf_converted(self):
        assert MarkdownExporter._cell("a\r\nb") == "a<br>b"


class TestExporterFactory:
    def test_defaults_available(self):
        assert ExporterFactory().available() == ("csv", "json", "markdown")

    def test_create_by_name_case_insensitive(self):
        assert isinstance(ExporterFactory().create("JSON"), JsonExporter)

    def test_for_path_by_extension(self):
        factory = ExporterFactory()
        assert isinstance(factory.for_path("x.CSV"), CsvExporter)
        assert isinstance(factory.for_path(Path("x.md")), MarkdownExporter)

    def test_unknown_name(self):
        with pytest.raises(ExportError, match="Unknown export format 'xml'") as info:
            ExporterFactory().create("xml")
        assert "Available formats" in info.value.hint

    def test_unknown_extension(self):
        with pytest.raises(ExportError, match="Cannot infer"):
            ExporterFactory().for_path("deck.xml")
        with pytest.raises(ExportError, match="'\\(none\\)'"):
            ExporterFactory().for_path("deck")

    def test_register_custom_exporter_as_decorator(self):
        factory = ExporterFactory(include_defaults=False)
        assert factory.available() == ()

        @factory.register
        class TxtExporter(Exporter):
            name = "txt"
            extension = ".txt"

            def render(self, deck: Deck) -> str:
                return "\n".join(f"{c.front}={c.back}" for c in deck.cards)

        assert factory.available() == ("txt",)
        assert isinstance(factory.for_path("a.txt"), TxtExporter)

    def test_register_rejects_bad_classes(self):
        factory = ExporterFactory()
        with pytest.raises(TypeError):
            factory.register(object)  # type: ignore[arg-type]

        class Nameless(Exporter):
            def render(self, deck: Deck) -> str:
                return ""

        with pytest.raises(ValueError):
            factory.register(Nameless)


class TestExportDeck:
    def test_writes_file_inferring_format(self, deck: Deck, tmp_path: Path):
        target = export_deck(deck, tmp_path / "out.csv")
        assert target.exists()
        assert target.read_text(encoding="utf-8").startswith("front,back")

    def test_explicit_format_overrides_extension(self, deck: Deck, tmp_path: Path):
        target = export_deck(deck, tmp_path / "out.txt", fmt="json")
        assert json.loads(target.read_text(encoding="utf-8"))["title"] == "Sample"

    def test_overwrites_existing_atomically(self, deck: Deck, tmp_path: Path):
        target = tmp_path / "out.json"
        target.write_text("old", encoding="utf-8")
        export_deck(deck, target)
        assert target.read_text(encoding="utf-8") != "old"
        assert [p.name for p in tmp_path.iterdir()] == ["out.json"]

    def test_directory_target_rejected(self, deck: Deck, tmp_path: Path):
        with pytest.raises(ExportError, match="is a directory"):
            export_deck(deck, tmp_path, fmt="json")

    def test_missing_parent_directory(self, deck: Deck, tmp_path: Path):
        with pytest.raises(ExportError, match="Could not write"):
            export_deck(deck, tmp_path / "missing" / "out.json")

    def test_temp_file_cleaned_up_when_replace_fails(
        self, deck: Deck, tmp_path: Path, monkeypatch
    ):
        def boom(src, dst):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(ExportError, match="No space left"):
            export_deck(deck, tmp_path / "out.json")
        assert list(tmp_path.iterdir()) == []

    def test_cleanup_tolerates_already_removed_temp(
        self, deck: Deck, tmp_path: Path, monkeypatch
    ):
        def boom(src, dst):
            os.unlink(src)  # simulate something else removing the temp file
            raise OSError(5, "I/O error")

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(ExportError):
            export_deck(deck, tmp_path / "out.json")
        assert list(tmp_path.iterdir()) == []

    def test_custom_factory(self, deck: Deck, tmp_path: Path):
        factory = ExporterFactory(include_defaults=False)

        @factory.register
        class Plain(Exporter):
            name = "plain"
            extension = ".plain"

            def render(self, deck: Deck) -> str:
                return str(len(deck))

        target = export_deck(deck, tmp_path / "x.plain", factory=factory)
        assert target.read_text(encoding="utf-8") == "2"


class TestExactOutputFormatting:
    def test_json_is_pretty_printed_with_two_space_indent(self):
        text = JsonExporter().render(Deck(cards=(Flashcard("Q", "A"),), title="T"))
        expected = "\n".join(
            [
                "{",
                '  "title": "T",',
                '  "cards": [',
                "    {",
                '      "front": "Q",',
                '      "back": "A"',
                "    }",
                "  ]",
                "}",
                "",
            ]
        )
        assert text == expected

    def test_csv_uses_unix_line_endings(self):
        deck = Deck(cards=(Flashcard("Q1", "A1"), Flashcard("Q2", "A2")))
        text = CsvExporter().render(deck)
        assert "\r" not in text
        assert text == "front,back,hint,tags\nQ1,A1,,\nQ2,A2,,\n"

    def test_markdown_rows_are_numbered_from_one(self, deck: Deck):
        lines = MarkdownExporter().render(deck).splitlines()
        assert lines[4].startswith("| 1 |") and lines[5].startswith("| 2 |")

    def test_register_requires_both_name_and_extension(self):
        factory = ExporterFactory(include_defaults=False)

        class NoExtension(Exporter):
            name = "noext"

            def render(self, deck: Deck) -> str:
                return ""

        class NoName(Exporter):
            extension = ".x"

            def render(self, deck: Deck) -> str:
                return ""

        for cls in (NoExtension, NoName):
            with pytest.raises(ValueError, match="must define 'name' and 'extension'"):
                factory.register(cls)
        with pytest.raises(TypeError, match="subclass of Exporter"):
            factory.register(str)  # type: ignore[arg-type]

    def test_temp_file_is_created_next_to_target(
        self, deck: Deck, tmp_path: Path, monkeypatch
    ):
        """Atomic rename only works on the same filesystem."""
        seen = {}
        real_replace = os.replace

        def spy(src, dst):
            seen["src"] = Path(src)
            real_replace(src, dst)

        monkeypatch.setattr(os, "replace", spy)
        target = tmp_path / "sub"
        target.mkdir()
        export_deck(deck, target / "out.json")
        assert seen["src"].parent == target
        assert seen["src"].name.startswith(".tmp-")

    def test_export_writes_utf8(self, tmp_path: Path):
        deck = Deck(cards=(Flashcard("日本", "語"),))
        target = export_deck(deck, tmp_path / "u.csv")
        assert "日本" in target.read_bytes().decode("utf-8")
