"""
Per-card validation and normalisation.

The validator is stateless apart from its (immutable) config and a module-level
pre-compiled regex, so a single instance is safe to use from many threads.

Security notes:

* Field types are checked explicitly - a ``front`` that is a list or number is
  rejected rather than coerced, so a malicious file can't smuggle structures
  into places that expect text.
* Control characters (other than tab/newline/CR) are rejected because they can
  be used to inject terminal escape sequences into CLI output.
* All text is NFC-normalised and length-limited, which also makes duplicate
  detection reliable.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional, Tuple

from .config import LoaderConfig
from .exceptions import InvalidCardError
from .models import Flashcard
from .parsers import _describe

# C0 controls except \t (09), \n (0A), \r (0D); plus DEL (7F).
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

REQUIRED_FIELDS: Tuple[str, ...] = ("front", "back")
OPTIONAL_FIELDS: Tuple[str, ...] = ("hint", "tags")


class CardValidator:
    """Validate raw JSON items and build :class:`Flashcard` objects."""

    __slots__ = ("_config",)

    def __init__(self, config: Optional[LoaderConfig] = None) -> None:
        self._config = config or LoaderConfig()

    @property
    def config(self) -> LoaderConfig:
        return self._config

    def validate(self, item: Any, index: int) -> Flashcard:
        """Return a normalised :class:`Flashcard` or raise :class:`InvalidCardError`.

        ``index`` is the zero-based position in the deck; messages show it
        one-based because that is how people count cards.
        """
        if not isinstance(item, dict):
            raise InvalidCardError(
                f"Card #{index + 1} must be a JSON object, got {_describe(item)}.",
                index=index,
            )

        front = self._required_text(item, "front", index)
        back = self._required_text(item, "back", index)
        hint = self._optional_text(item, "hint", index)
        tags = self._optional_tags(item, index)
        return Flashcard(front=front, back=back, hint=hint, tags=tags)

    def _required_text(self, item: dict, key: str, index: int) -> str:
        if key not in item:
            raise InvalidCardError(
                f"Card #{index + 1} is missing the required '{key}' field.",
                index=index,
                field=key,
            )
        text = self._clean_text(item[key], key, index)
        if text is None or not text:
            raise InvalidCardError(
                f"Card #{index + 1} has an empty '{key}' field.",
                index=index,
                field=key,
            )
        return text

    def _optional_text(self, item: dict, key: str, index: int) -> Optional[str]:
        if key not in item or item[key] is None:
            return None
        text = self._clean_text(item[key], key, index)
        return text or None

    def _clean_text(self, value: Any, key: str, index: int) -> Optional[str]:
        if not isinstance(value, str):
            raise InvalidCardError(
                f"Card #{index + 1} field '{key}' must be text, "
                f"got {_describe(value)}.",
                index=index,
                field=key,
            )
        limit = self._config.max_field_length
        if len(value) > limit:
            raise InvalidCardError(
                f"Card #{index + 1} field '{key}' is too long "
                f"({len(value)} characters; limit is {limit}).",
                index=index,
                field=key,
                hint=f"Shorten the text or raise 'max_field_length' above {limit}.",
            )
        if _CONTROL_CHARS.search(value):
            raise InvalidCardError(
                f"Card #{index + 1} field '{key}' contains control characters.",
                index=index,
                field=key,
                hint="Remove non-printable characters; "
                "only tab and newline are allowed.",
            )
        return unicodedata.normalize("NFC", value).strip()

    def _optional_tags(self, item: dict, index: int) -> Tuple[str, ...]:
        raw = item.get("tags")
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise InvalidCardError(
                f"Card #{index + 1} field 'tags' must be an array of strings, "
                f"got {_describe(raw)}.",
                index=index,
                field="tags",
            )
        if len(raw) > self._config.max_tags:
            raise InvalidCardError(
                f"Card #{index + 1} has {len(raw)} tags; limit is "
                f"{self._config.max_tags}.",
                index=index,
                field="tags",
            )
        seen: set[str] = set()
        tags: list[str] = []
        for position, tag in enumerate(raw):
            if not isinstance(tag, str):
                raise InvalidCardError(
                    f"Card #{index + 1} tag {position + 1} must be text, "
                    f"got {_describe(tag)}.",
                    index=index,
                    field="tags",
                )
            if len(tag) > self._config.max_tag_length or _CONTROL_CHARS.search(tag):
                raise InvalidCardError(
                    f"Card #{index + 1} tag {position + 1} is too long or contains "
                    f"control characters.",
                    index=index,
                    field="tags",
                )
            cleaned = unicodedata.normalize("NFC", tag).strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                tags.append(cleaned)
        return tuple(tags)
