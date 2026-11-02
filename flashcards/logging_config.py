"""
Logging configuration.

The ``flashcards`` package only attaches a ``NullHandler`` on import (library
best practice) so it never spams a host application. The CLI calls
:func:`configure_logging` to opt in. The function is idempotent: handlers it
previously installed are removed first, so repeated calls (tests, REPLs) do
not accumulate handlers - a common and subtle resource leak.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional, TextIO, Union

LOGGER_NAME = "flashcards"
_MARKER = "_flashcards_managed"
DEFAULT_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return the package logger or a child of it."""
    return logging.getLogger(LOGGER_NAME if not name else f"{LOGGER_NAME}.{name}")


def _resolve_level(level: Union[int, str]) -> int:
    if isinstance(level, int):
        return level
    resolved = logging.getLevelName(level.upper())
    if not isinstance(resolved, int):
        raise ValueError(f"Unknown log level {level!r}")
    return resolved


def reset_logging() -> None:
    """Remove and close every handler installed by :func:`configure_logging`."""
    root = logging.getLogger(LOGGER_NAME)
    for handler in list(root.handlers):
        if getattr(handler, _MARKER, False):
            root.removeHandler(handler)
            handler.close()


def configure_logging(
    level: Union[int, str] = logging.INFO,
    *,
    log_file: Optional[Union[str, "os.PathLike[str]"]] = None,
    stream: Optional[TextIO] = None,
    fmt: str = DEFAULT_FORMAT,
) -> logging.Logger:
    """Install console and/or file handlers on the ``flashcards`` logger.

    Args:
        level: Minimum level to emit (name or numeric).
        log_file: If given, append log records to this file (UTF-8).
        stream: Console stream. When ``log_file`` is omitted this defaults to
            ``sys.stderr``; when ``log_file`` is given, console output is only
            added if ``stream`` is passed explicitly.
    """
    reset_logging()
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(_resolve_level(level))
    logger.propagate = False
    formatter = logging.Formatter(fmt)

    handlers: list[logging.Handler] = []
    if log_file is not None:
        handlers.append(logging.FileHandler(os.fspath(log_file), encoding="utf-8"))
    if stream is not None or log_file is None:
        handlers.append(logging.StreamHandler(stream or sys.stderr))

    for handler in handlers:
        handler.setFormatter(formatter)
        setattr(handler, _MARKER, True)
        logger.addHandler(handler)
    return logger
