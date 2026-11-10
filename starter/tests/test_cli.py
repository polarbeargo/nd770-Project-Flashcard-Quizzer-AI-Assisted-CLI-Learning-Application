"""End-to-end tests for the CLI (main.py) - every failure must be friendly."""

from __future__ import annotations

import builtins
import io
import json
import logging
from pathlib import Path

import pytest

import main
from flashcards import FlashcardError, LoaderConfig

from .conftest import ARRAY_DECK, OBJECT_DECK


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main.run(list(argv), out=out, err=err)
    return code, out.getvalue(), err.getvalue()


class TestValidate:
    def test_array_file(self, write_json):
        path = write_json(ARRAY_DECK)
        code, out, err = run_cli("validate", str(path))
        assert code == main.EXIT_OK
        assert "OK: 2 card(s)" in out and "[array format]" in out
        assert err == ""

    def test_object_file_shows_title(self, write_json):
        path = write_json(OBJECT_DECK)
        code, out, _ = run_cli("validate", str(path))
        assert code == 0 and "'Demo'" in out and "[object format]" in out

    def test_malformed_json_is_friendly(self, write_json):
        path = write_json("[{oops}]")
        code, out, err = run_cli("validate", str(path))
        assert code == main.EXIT_USER_ERROR
        assert err.startswith("Error: ")
        assert "Not valid JSON" in err and "Hint:" in err
        assert "Traceback" not in err and out == ""

    def test_missing_field_is_friendly(self, write_json):
        path = write_json([{"front": "only"}])
        code, _, err = run_cli("validate", str(path))
        assert code == 1 and "missing the required 'back'" in err

    def test_missing_file(self, tmp_path: Path):
        code, _, err = run_cli("validate", str(tmp_path / "nope.json"))
        assert code == 1 and "Could not find the file" in err

    def test_skip_invalid_prints_warnings_and_summary(self, write_json):
        path = write_json(
            [{"front": "Q", "back": "A"}, {"front": "Q"}, {"front": "Q", "back": "A"}]
        )
        code, out, err = run_cli("validate", str(path), "--skip-invalid")
        assert code == 0
        assert "Warning: Card #2 is missing" in err
        assert "Warning: Card #3 duplicates" in err
        assert "1 invalid card(s) skipped, 1 duplicate(s) removed" in out

    def test_quiet_suppresses_warnings(self, write_json):
        path = write_json([{"front": "Q", "back": "A"}, {"front": "Q"}])
        code, _, err = run_cli("validate", str(path), "--skip-invalid", "--quiet")
        assert code == 0 and err == ""

    def test_keep_duplicates_flag(self, write_json):
        path = write_json([{"front": "Q", "back": "A"}] * 2)
        code, out, _ = run_cli("validate", str(path), "--keep-duplicates")
        assert code == 0 and "OK: 2 card(s)" in out

    def test_allow_empty_flag(self, write_json):
        path = write_json([])
        assert run_cli("validate", str(path))[0] == 1
        code, out, _ = run_cli("validate", str(path), "--allow-empty")
        assert code == 0 and "OK: 0 card(s)" in out

    def test_config_file_and_env_layering(
        self, write_json, tmp_path: Path, monkeypatch
    ):
        deck = write_json(ARRAY_DECK)
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"max_cards": 1}), encoding="utf-8")
        code, _, err = run_cli("validate", str(deck), "--config", str(cfg))
        assert code == 1 and "limit is 1" in err
        monkeypatch.setenv("FLASHCARD_MAX_CARDS", "50")
        assert run_cli("validate", str(deck), "--config", str(cfg))[0] == 0

    def test_bad_config_file_is_friendly(self, write_json, tmp_path: Path):
        deck = write_json(ARRAY_DECK)
        code, _, err = run_cli(
            "validate", str(deck), "--config", str(tmp_path / "x.json")
        )
        assert code == 1 and "Config file not found" in err

    def test_unsupported_url_scheme(self):
        code, _, err = run_cli("validate", "ftp://example.com/deck.json")
        assert code == 1 and "Unsupported URL scheme" in err

    def test_remote_deck_via_fake_fetcher(self, monkeypatch):
        monkeypatch.setattr(
            "flashcards.remote.fetch_text", lambda url, **kw: json.dumps(OBJECT_DECK)
        )
        code, out, _ = run_cli("validate", "https://example.com/deck.json")
        assert code == 0 and "https://example.com/deck.json" in out


class TestShow:
    def test_prints_cards(self, write_json):
        path = write_json(OBJECT_DECK)
        code, out, _ = run_cli("show", str(path))
        assert code == 0
        assert "Demo (2 cards)" in out
        assert "1. Q: Q1" in out and "   A: A1" in out
        assert "Hint: h" in out and "Tags: t1, t2" in out

    def test_limit(self, write_json):
        path = write_json(ARRAY_DECK)
        code, out, _ = run_cli("show", str(path), "--limit", "1")
        assert code == 0 and "2. Q:" not in out and "... 1 more card(s)" in out

    def test_negative_limit_is_user_error(self, write_json):
        path = write_json(ARRAY_DECK)
        code, _, err = run_cli("show", str(path), "--limit", "-1")
        assert code == 1 and "--limit must be zero or a positive" in err

    def test_untitled_deck_uses_default_heading(self, write_json):
        path = write_json(ARRAY_DECK)
        assert "Deck (2 cards)" in run_cli("show", str(path))[1]


class TestExport:
    def test_export_by_extension(self, write_json, tmp_path: Path):
        path = write_json(OBJECT_DECK)
        target = tmp_path / "out.md"
        code, out, _ = run_cli("export", str(path), str(target))
        assert code == 0 and "Exported 2 card(s)" in out
        assert target.read_text(encoding="utf-8").startswith("# Demo")

    def test_export_explicit_format(self, write_json, tmp_path: Path):
        path = write_json(ARRAY_DECK)
        target = tmp_path / "out.dat"
        code, _, _ = run_cli("export", str(path), str(target), "--format", "csv")
        assert code == 0 and target.read_text(encoding="utf-8").startswith("front,back")

    def test_export_unknown_extension_is_friendly(self, write_json, tmp_path: Path):
        path = write_json(ARRAY_DECK)
        code, _, err = run_cli("export", str(path), str(tmp_path / "out.xml"))
        assert code == 1 and "Cannot infer an export format" in err

    def test_export_bad_format_choice_is_argparse_error(
        self, write_json, tmp_path: Path
    ):
        path = write_json(ARRAY_DECK)
        with pytest.raises(SystemExit) as info:
            run_cli("export", str(path), str(tmp_path / "o.json"), "--format", "xml")
        assert info.value.code == 2


class TestQuiz:
    def test_quiz_command_uses_sequential_mode_by_default(
        self, write_json, monkeypatch
    ):
        path = write_json(ARRAY_DECK)
        answers = iter(("a1", "a2"))
        monkeypatch.setattr(builtins, "input", lambda: next(answers))

        code, out, err = run_cli("quiz", str(path))

        assert code == main.EXIT_OK
        assert err == ""
        assert "(2 cards; sequential mode)" in out
        assert "| Total questions answered | 2 |" in out
        assert "| Accuracy | 100.0% |" in out

    def test_quiz_command_accepts_file_mode_alias_and_stats(
        self, write_json, monkeypatch
    ):
        path = write_json(ARRAY_DECK)
        answers = iter(("a1", "a2"))
        monkeypatch.setattr(builtins, "input", lambda: next(answers))

        code, out, err = run_cli("quiz", "-f", str(path), "-m", "sequential", "--stats")

        assert code == main.EXIT_OK
        assert err == ""
        assert "(2 cards; sequential mode)" in out
        assert "| Correct answers | 2 |" in out

    def test_quiz_command_still_accepts_positional_source(
        self, write_json, monkeypatch
    ):
        path = write_json(ARRAY_DECK)
        answers = iter(("exit",))
        monkeypatch.setattr(builtins, "input", lambda: next(answers))

        code, out, err = run_cli("quiz", str(path))

        assert code == main.EXIT_OK
        assert err == ""
        assert "| Total questions answered | 0 |" in out

    def test_quiz_command_handles_keyboard_interrupt(self, write_json, monkeypatch):
        path = write_json(ARRAY_DECK)

        def interrupt():
            raise KeyboardInterrupt

        monkeypatch.setattr(builtins, "input", interrupt)
        code, out, err = run_cli("quiz", str(path))

        assert code == main.EXIT_OK
        assert err == ""
        assert "Quiz interrupted." in out
        assert "Quiz summary" in out
        assert "Traceback" not in out

    @pytest.mark.parametrize(
        ("arguments", "message"),
        [
            ((), "A quiz deck is required"),
            (("deck.json", "-f", "other.json"), "Provide the quiz deck once"),
        ],
    )
    def test_quiz_command_requires_exactly_one_deck_source(self, arguments, message):
        code, out, err = run_cli("quiz", *arguments)
        assert code == main.EXIT_USER_ERROR
        assert out == ""
        assert message in err

    def test_quiz_command_uses_selected_mode_and_retries_misses(
        self, write_json, monkeypatch
    ):
        path = write_json(ARRAY_DECK)
        answers = iter(("wrong", "a2", "a1"))
        monkeypatch.setattr(builtins, "input", lambda: next(answers))

        code, out, err = run_cli("quiz", str(path), "--mode", "adaptive")

        assert code == main.EXIT_OK
        assert err == ""
        assert "(2 cards; adaptive mode)" in out
        assert out.count("Question ") == 3
        assert "| Missed terms | Q1 |" in out

    def test_quiz_command_reports_loader_errors_without_traceback(self, write_json):
        path = write_json("[{oops}]")
        code, out, err = run_cli("quiz", str(path))
        assert code == main.EXIT_USER_ERROR
        assert out == ""
        assert "Not valid JSON" in err
        assert "Traceback" not in err

    def test_quiz_command_rejects_unknown_mode(self, write_json):
        path = write_json(ARRAY_DECK)
        with pytest.raises(SystemExit) as info:
            run_cli("quiz", str(path), "--mode", "other")
        assert info.value.code == 2


class TestFormatsAndMisc:
    def test_formats_lists_everything(self):
        code, out, _ = run_cli("formats")
        assert code == 0
        assert "array" in out and "object" in out
        assert "csv (.csv)" in out and "markdown (.md)" in out

    def test_no_command_is_usage_error(self):
        with pytest.raises(SystemExit) as info:
            run_cli()
        assert info.value.code == 2

    def test_debug_logs_to_stderr(self, write_json):
        path = write_json(ARRAY_DECK)
        code, _, err = run_cli("validate", str(path), "--debug")
        assert code == 0 and "DEBUG" in err and "Detected array format" in err

    def test_log_file_option(self, write_json, tmp_path: Path):
        path = write_json(ARRAY_DECK)
        log_file = tmp_path / "run.log"
        code, _, err = run_cli("validate", str(path), "--log-file", str(log_file))
        assert code == 0 and err == ""
        main_logger = logging.getLogger("flashcards")
        for handler in list(main_logger.handlers):
            handler.flush()
        assert "Loaded 2 card(s)" in log_file.read_text(encoding="utf-8")

    def test_unexpected_exception_is_contained(self, write_json, monkeypatch):
        path = write_json(ARRAY_DECK)

        def explode(self, source):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(main.FlashcardLoader, "load", explode)
        code, _, err = run_cli("validate", str(path))
        assert code == main.EXIT_UNEXPECTED
        assert "Unexpected error: RuntimeError: kaboom" in err
        assert "Traceback" not in err

    def test_keyboard_interrupt_is_contained(self, write_json, monkeypatch):
        path = write_json(ARRAY_DECK)

        def interrupt(self, source):
            raise KeyboardInterrupt

        monkeypatch.setattr(main.FlashcardLoader, "load", interrupt)
        code, _, err = run_cli("validate", str(path))
        assert code == main.EXIT_INTERRUPTED and "Interrupted" in err

    def test_subscriptions_are_released_after_run(self, write_json, monkeypatch):
        path = write_json(ARRAY_DECK)
        seen = {}
        original = main.FlashcardLoader

        class Spy(original):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                seen["loader"] = self

        monkeypatch.setattr(main, "FlashcardLoader", Spy)
        run_cli("validate", str(path))
        assert len(seen["loader"].events) == 0

    def test_main_calls_sys_exit(self, write_json):
        path = write_json(ARRAY_DECK)
        with pytest.raises(SystemExit) as info:
            main.main(["validate", str(path), "--quiet"])
        assert info.value.code == 0

    def test_build_config_defaults(self):
        args = main.build_parser().parse_args(["validate", "x.json"])
        assert main.build_config(args) == LoaderConfig()

    def test_flashcard_error_without_hint(self, write_json, monkeypatch):
        path = write_json(ARRAY_DECK)

        def fail(self, source):
            raise FlashcardError("plain failure", hint="")

        monkeypatch.setattr(main.FlashcardLoader, "load", fail)
        code, _, err = run_cli("validate", str(path))
        assert code == 1 and err == "Error: plain failure\n"


class TestOutputDetails:
    """Pin down exact CLI behaviour that mutation testing showed was unverified."""

    def test_validate_untitled_deck_has_no_empty_quotes(self, write_json):
        path = write_json(ARRAY_DECK)
        _, out, _ = run_cli("validate", str(path))
        assert "''" not in out

    def test_summary_line_appears_when_only_cards_were_skipped(self, write_json):
        path = write_json([{"front": "Q", "back": "A"}, {"front": "bad"}])
        _, out, _ = run_cli("validate", str(path), "--skip-invalid", "-q")
        assert "1 invalid card(s) skipped, 0 duplicate(s) removed" in out

    def test_summary_line_absent_for_clean_deck(self, write_json):
        path = write_json(ARRAY_DECK)
        _, out, _ = run_cli("validate", str(path))
        assert "skipped" not in out

    def test_show_separator_and_no_more_line_without_limit(self, write_json):
        path = write_json(ARRAY_DECK)
        _, out, _ = run_cli("show", str(path))
        lines = out.splitlines()
        assert lines[1] == "-" * 40
        assert "more card(s)" not in out

    def test_show_limit_equal_to_size_has_no_more_line(self, write_json):
        path = write_json(ARRAY_DECK)
        _, out, _ = run_cli("show", str(path), "--limit", "2")
        assert "more card(s)" not in out

    def test_log_file_without_debug_is_info_level(self, write_json, tmp_path: Path):
        path = write_json(ARRAY_DECK)
        log_file = tmp_path / "info.log"
        run_cli("validate", str(path), "--log-file", str(log_file))
        from flashcards.logging_config import reset_logging

        reset_logging()
        text = log_file.read_text(encoding="utf-8")
        assert "INFO" in text and "DEBUG" not in text

    def test_log_file_with_debug_is_debug_level(self, write_json, tmp_path: Path):
        path = write_json(ARRAY_DECK)
        log_file = tmp_path / "debug.log"
        code, _, err = run_cli(
            "validate", str(path), "--log-file", str(log_file), "--debug"
        )
        from flashcards.logging_config import reset_logging

        reset_logging()
        assert code == 0 and err == ""  # file only, nothing on stderr
        assert "DEBUG" in log_file.read_text(encoding="utf-8")

    def test_debug_logs_user_error_with_traceback_to_log_only(self, write_json):
        path = write_json("[{oops}]")
        code, out, err = run_cli("validate", str(path), "--debug")
        assert code == 1 and out == ""
        assert "User-facing error" in err and "Traceback" in err
        # ...but the user-facing block itself is still the friendly one.
        assert err.rstrip().splitlines()[-2].startswith("Error: ")

    def test_debug_logs_unexpected_failure(self, write_json, monkeypatch):
        path = write_json(ARRAY_DECK)

        def explode(self, source):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(main.FlashcardLoader, "load", explode)
        code, _, err = run_cli("validate", str(path), "--debug")
        assert code == 2 and "Unexpected failure" in err

    def test_no_debug_means_no_traceback_anywhere(self, write_json):
        path = write_json("[{oops}]")
        _, out, err = run_cli("validate", str(path))
        assert "Traceback" not in err + out

    def test_short_format_flag(self, write_json, tmp_path: Path):
        path = write_json(ARRAY_DECK)
        target = tmp_path / "out.dat"
        code, _, _ = run_cli("export", str(path), str(target), "-f", "markdown")
        assert code == 0 and target.read_text(encoding="utf-8").startswith("# ")
