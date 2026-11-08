"""
Flashcard Quizzer - command-line entry point.

Usage examples::

    python main.py validate data/samples/python_basics_array.json
    python main.py show data/samples/python_basics_object.json --limit 3
    python main.py export deck.json deck.csv
    python main.py formats

Every failure is reported as a short, friendly message - never a traceback.
Pass ``--debug`` to also log full diagnostics (to stderr or ``--log-file``).
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Callable, Dict, List, Optional, Sequence, TextIO

from flashcards import (
    EventKind,
    FlashcardError,
    FlashcardLoader,
    LoaderConfig,
    LoadEvent,
    export_deck,
    log_event,
)
from flashcards.exporters import DEFAULT_FACTORY
from flashcards.logging_config import configure_logging, get_logger

EXIT_OK = 0
EXIT_USER_ERROR = 1
EXIT_UNEXPECTED = 2
EXIT_INTERRUPTED = 130

logger = get_logger("cli")


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config",
        metavar="FILE",
        help="JSON file with loader settings (FLASHCARD_* env vars also apply).",
    )
    common.add_argument(
        "--skip-invalid",
        action="store_true",
        help="Skip cards that fail validation instead of stopping at the first one.",
    )
    common.add_argument(
        "--allow-empty",
        action="store_true",
        help="Treat a deck with zero valid cards as success.",
    )
    common.add_argument(
        "--keep-duplicates",
        action="store_true",
        help="Do not remove cards whose front/back repeat an earlier card.",
    )
    common.add_argument(
        "--debug", action="store_true", help="Log detailed diagnostics."
    )
    common.add_argument("--log-file", metavar="FILE", help="Append logs to FILE.")
    common.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress warnings on stderr."
    )

    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Load, validate and export flashcard decks.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    validate = sub.add_parser(
        "validate", parents=[common], help="Check that a deck file is well-formed."
    )
    validate.add_argument("source", help="Path or http(s) URL of a JSON deck.")

    show = sub.add_parser(
        "show", parents=[common], help="Validate a deck and print its cards."
    )
    show.add_argument("source", help="Path or http(s) URL of a JSON deck.")
    show.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help="Only print the first N cards.",
    )

    export = sub.add_parser(
        "export", parents=[common], help="Convert a deck to another format."
    )
    export.add_argument("source", help="Path or http(s) URL of a JSON deck.")
    export.add_argument("output", help="Destination file (extension picks the format).")
    export.add_argument(
        "--format",
        "-f",
        choices=DEFAULT_FACTORY.available(),
        help="Explicit output format (overrides the file extension).",
    )

    sub.add_parser("formats", help="List supported input and export formats.")
    return parser


# --------------------------------------------------------------------------- #
# Wiring helpers
# --------------------------------------------------------------------------- #


def build_config(args: argparse.Namespace) -> LoaderConfig:
    """Layer config sources: defaults < --config file < env vars < CLI flags."""
    config = LoaderConfig.from_file(args.config) if args.config else LoaderConfig()
    config = LoaderConfig.from_env(base=config)
    overrides: Dict[str, object] = {}
    if args.skip_invalid:
        overrides["on_invalid_card"] = "skip"
    if args.allow_empty:
        overrides["allow_empty"] = True
    if args.keep_duplicates:
        overrides["dedupe"] = False
    return config.replace(**overrides) if overrides else config


def make_warning_printer(stream: TextIO) -> Callable[[LoadEvent], None]:
    """Observer that echoes skip/duplicate events to the user."""

    def _print(event: LoadEvent) -> None:
        if event.kind in (EventKind.CARD_SKIPPED, EventKind.DUPLICATE_REMOVED):
            print(f"Warning: {event.message}", file=stream)

    return _print


def _setup_logging(args: argparse.Namespace, err: TextIO) -> None:
    if args.debug or args.log_file:
        level = logging.DEBUG if args.debug else logging.INFO
        if args.log_file:
            configure_logging(level, log_file=args.log_file)
        else:
            configure_logging(level, stream=err)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def cmd_validate(args: argparse.Namespace, loader: FlashcardLoader, out: TextIO) -> int:
    deck = loader.load(args.source)
    title = f" '{deck.title}'" if deck.title else ""
    print(
        f"OK: {len(deck)} card(s) loaded from {deck.source}{title} "
        f"[{deck.format_name} format]",
        file=out,
    )
    if deck.skipped or deck.duplicates_removed:
        print(
            f"    {deck.skipped} invalid card(s) skipped, "
            f"{deck.duplicates_removed} duplicate(s) removed",
            file=out,
        )
    return EXIT_OK


def cmd_show(args: argparse.Namespace, loader: FlashcardLoader, out: TextIO) -> int:
    if args.limit < 0:
        raise FlashcardError("--limit must be zero or a positive number.")
    deck = loader.load(args.source)
    cards = deck.cards[: args.limit] if args.limit else deck.cards
    print(f"{deck.title or 'Deck'} ({len(deck)} cards)", file=out)
    print("-" * 40, file=out)
    for number, card in enumerate(cards, start=1):
        print(f"{number}. Q: {card.front}", file=out)
        print(f"   A: {card.back}", file=out)
        if card.hint:
            print(f"   Hint: {card.hint}", file=out)
        if card.tags:
            print(f"   Tags: {', '.join(card.tags)}", file=out)
    if len(cards) < len(deck):
        print(f"... {len(deck) - len(cards)} more card(s)", file=out)
    return EXIT_OK


def cmd_export(args: argparse.Namespace, loader: FlashcardLoader, out: TextIO) -> int:
    deck = loader.load(args.source)
    target = export_deck(deck, args.output, fmt=args.format)
    print(f"Exported {len(deck)} card(s) to {target}", file=out)
    return EXIT_OK


def cmd_formats(out: TextIO) -> int:
    print("Input formats (JSON):", file=out)
    print('  array   [{"front": "...", "back": "..."}, ...]', file=out)
    print(
        '  object  {"title": "...", "cards": [{"front": "...", "back": "..."}]}',
        file=out,
    )
    print("Export formats:", file=out)
    for name in DEFAULT_FACTORY.available():
        print(f"  {name} ({DEFAULT_FACTORY.create(name).extension})", file=out)
    return EXIT_OK


COMMANDS: Dict[str, Callable[[argparse.Namespace, FlashcardLoader, TextIO], int]] = {
    "validate": cmd_validate,
    "show": cmd_show,
    "export": cmd_export,
}


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def run(
    argv: Optional[Sequence[str]] = None,
    *,
    out: Optional[TextIO] = None,
    err: Optional[TextIO] = None,
) -> int:
    """Run the CLI and return an exit code (never raises for user errors)."""
    out = out or sys.stdout
    err = err or sys.stderr
    args = build_parser().parse_args(argv)

    if args.command == "formats":
        return cmd_formats(out)

    try:
        _setup_logging(args, err)
        loader = FlashcardLoader(build_config(args))
        subscriptions = [loader.events.subscribe(log_event)]
        if not args.quiet:
            subscriptions.append(loader.events.subscribe(make_warning_printer(err)))
        try:
            return COMMANDS[args.command](args, loader, out)
        finally:
            for subscription in subscriptions:
                subscription.unsubscribe()
    except FlashcardError as exc:
        logger.debug("User-facing error", exc_info=True)
        print(f"Error: {exc.user_message()}", file=err)
        return EXIT_USER_ERROR
    except KeyboardInterrupt:
        print("\nInterrupted.", file=err)
        return EXIT_INTERRUPTED
    except Exception as exc:  # noqa: BLE001 - last line of defence, no tracebacks
        logger.exception("Unexpected failure")
        print(
            f"Unexpected error: {type(exc).__name__}: {exc}\n"
            "  Hint: re-run with --debug for diagnostics, and please report this bug.",
            file=err,
        )
        return EXIT_UNEXPECTED


def main(argv: Optional[List[str]] = None) -> None:
    sys.exit(run(argv))


if __name__ == "__main__":
    main()
