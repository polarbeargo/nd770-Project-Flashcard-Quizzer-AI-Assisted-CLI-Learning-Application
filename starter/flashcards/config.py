"""
Configuration management for the loader.

``LoaderConfig`` is an immutable value object, so a single instance can be
shared by many loaders and threads. It can be built from code, from a JSON
file, or from ``FLASHCARD_*`` environment variables, with every value
validated up-front so bad settings fail fast with a friendly ``ConfigError``.
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union

from .exceptions import ConfigError

ENV_PREFIX = "FLASHCARD_"
INVALID_CARD_POLICIES = ("raise", "skip")
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True, slots=True)
class LoaderConfig:
    """Tunable limits and behaviours for :class:`~flashcards.loader.FlashcardLoader`.

    Attributes:
        max_file_bytes: Reject inputs larger than this before reading them.
        max_cards: Reject decks with more cards than this.
        max_field_length: Maximum characters allowed in ``front``/``back``/``hint``.
        max_tags: Maximum number of tags per card.
        max_tag_length: Maximum characters per tag.
        on_invalid_card: ``"raise"`` to fail on the first bad card, or
            ``"skip"`` to drop bad cards and report them via events.
        dedupe: Remove cards whose ``front``/``back`` exactly match an earlier card.
        allow_empty: Permit decks that end up with zero cards.
        encoding: Text encoding used to read files.
        cache_size: Number of parsed files kept in the loader's LRU cache
            (``0`` disables caching).
        request_timeout: Seconds to wait when fetching a deck over HTTP(S).
    """

    max_file_bytes: int = 10 * 1024 * 1024
    max_cards: int = 10_000
    max_field_length: int = 2_000
    max_tags: int = 20
    max_tag_length: int = 50
    on_invalid_card: str = "raise"
    dedupe: bool = True
    allow_empty: bool = False
    encoding: str = "utf-8"
    cache_size: int = 8
    request_timeout: float = 10.0

    def __post_init__(self) -> None:
        for name in (
            "max_file_bytes",
            "max_cards",
            "max_field_length",
            "max_tags",
            "max_tag_length",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ConfigError(
                    f"'{name}' must be a positive integer, got {value!r}."
                )
        if not isinstance(self.cache_size, int) or self.cache_size < 0:
            raise ConfigError(
                f"'cache_size' must be a non-negative integer, got {self.cache_size!r}."
            )
        if self.on_invalid_card not in INVALID_CARD_POLICIES:
            raise ConfigError(
                f"'on_invalid_card' must be one of {INVALID_CARD_POLICIES}, "
                f"got {self.on_invalid_card!r}."
            )
        if not isinstance(self.request_timeout, (int, float)) or isinstance(
            self.request_timeout, bool
        ):
            raise ConfigError("'request_timeout' must be a number.")
        try:
            valid_timeout = math.isfinite(self.request_timeout) and (
                self.request_timeout > 0
            )
        except OverflowError:
            valid_timeout = False
        if not valid_timeout:
            raise ConfigError("'request_timeout' must be finite and greater than zero.")
        for name in ("dedupe", "allow_empty"):
            if not isinstance(getattr(self, name), bool):
                raise ConfigError(f"'{name}' must be true or false.")
        try:
            "".encode(self.encoding)
        except (LookupError, TypeError):
            raise ConfigError(f"Unknown text encoding {self.encoding!r}.") from None

    def replace(self, **overrides: Any) -> "LoaderConfig":
        """Return a copy with the given fields changed (validated)."""
        unknown = set(overrides) - {f.name for f in fields(self)}
        if unknown:
            raise ConfigError(
                f"Unknown config option(s): {', '.join(sorted(unknown))}."
            )
        return dataclasses.replace(self, **overrides)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "LoaderConfig":
        """Build from a dict-like object (e.g. parsed JSON)."""
        return cls().replace(**dict(data))

    @classmethod
    def from_file(cls, path: Union[str, os.PathLike[str]]) -> "LoaderConfig":
        """Load settings from a JSON file containing a single object."""
        file_path = Path(path)
        try:
            text = file_path.read_text(encoding="utf-8")
            data = json.loads(text)
        except FileNotFoundError:
            raise ConfigError(f"Config file not found: {file_path}") from None
        except OSError as exc:
            raise ConfigError(
                f"Could not read config file {file_path}: {exc}"
            ) from None
        except json.JSONDecodeError as exc:
            raise ConfigError(
                f"Config file {file_path} is not valid JSON "
                f"(line {exc.lineno}, column {exc.colno}): {exc.msg}."
            ) from None
        if not isinstance(data, dict):
            raise ConfigError("Config file must contain a single JSON object.")
        return cls.from_mapping(data)

    @classmethod
    def from_env(
        cls,
        environ: Optional[Mapping[str, str]] = None,
        *,
        prefix: str = ENV_PREFIX,
        base: Optional["LoaderConfig"] = None,
    ) -> "LoaderConfig":
        """Overlay ``PREFIX<FIELD>`` environment variables onto ``base``.

        Example: ``FLASHCARD_MAX_CARDS=500 FLASHCARD_DEDUPE=false``.
        """
        env = os.environ if environ is None else environ
        base_config = cls() if base is None else base
        overrides: Dict[str, Any] = {}
        for spec in fields(cls):
            raw = env.get(f"{prefix}{spec.name.upper()}")
            if raw is None:
                continue
            overrides[spec.name] = _coerce(spec.name, spec.type, raw)
        return base_config.replace(**overrides) if overrides else base_config


def _coerce(name: str, declared_type: Any, raw: str) -> Any:
    """Convert an environment-variable string to the field's declared type."""
    type_name = (
        declared_type if isinstance(declared_type, str) else declared_type.__name__
    )
    value = raw.strip()
    try:
        if type_name == "bool":
            lowered = value.lower()
            if lowered in _TRUE_VALUES:
                return True
            if lowered in _FALSE_VALUES:
                return False
            raise ValueError
        if type_name == "int":
            return int(value)
        if type_name == "float":
            return float(value)
    except ValueError:
        raise ConfigError(
            f"Environment value for '{name}' ({raw!r}) is not a valid {type_name}."
        ) from None
    return value
