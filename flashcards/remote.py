"""
External integration: fetch deck JSON over HTTP(S) with the standard library.

Hardening:

* Only ``http`` and ``https`` schemes are accepted (no ``file://`` reads).
* A connect/read timeout is always applied.
* The response body is read with a hard byte cap so a hostile or
  misconfigured server cannot exhaust memory.
* All network failures surface as a single friendly :class:`RemoteFetchError`.

The ``opener`` parameter exists for dependency injection in tests; production
code uses :func:`urllib.request.urlopen`.
"""

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from .exceptions import FileTooLargeError, MalformedJSONError, RemoteFetchError

ALLOWED_SCHEMES = frozenset({"http", "https"})
USER_AGENT = "flashcard-quizzer/1.0 (+https://github.com/polarbeargo)"

Opener = Callable[..., Any]


def validate_url(url: str) -> str:
    """Return ``url`` if it is an absolute http(s) URL, else raise."""
    if not isinstance(url, str) or not url.strip():
        raise RemoteFetchError("The URL is empty.")
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise RemoteFetchError(
            f"Unsupported URL scheme {parsed.scheme or '(none)'!r}; "
            "only http and https are allowed."
        )
    if not parsed.netloc:
        raise RemoteFetchError(f"The URL {url!r} has no host name.")
    return url.strip()


def fetch_text(
    url: str,
    *,
    timeout: float = 10.0,
    max_bytes: int = 10 * 1024 * 1024,
    encoding: str = "utf-8",
    opener: Optional[Opener] = None,
) -> str:
    """Download ``url`` and return its body as text."""
    url = validate_url(url)
    open_url = opener or urllib.request.urlopen
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with open_url(request, timeout=timeout) as response:
            declared = response.headers.get("Content-Length")
            if (
                declared is not None
                and declared.isdigit()
                and int(declared) > max_bytes
            ):
                raise FileTooLargeError(
                    f"The server reports {int(declared):,} bytes; "
                    f"the limit is {max_bytes:,} bytes.",
                    source=url,
                )
            body: bytes = response.read(max_bytes + 1)
    except FileTooLargeError:
        raise
    except urllib.error.HTTPError as exc:
        raise RemoteFetchError(
            f"The server at {url!r} responded with HTTP {exc.code} {exc.reason}."
        ) from None
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise RemoteFetchError(f"Timed out fetching {url!r}.") from None
        raise RemoteFetchError(f"Could not reach {url!r}: {reason}.") from None
    except (socket.timeout, TimeoutError):
        raise RemoteFetchError(f"Timed out fetching {url!r}.") from None
    except OSError as exc:
        raise RemoteFetchError(f"Network error fetching {url!r}: {exc}.") from None

    if len(body) > max_bytes:
        raise FileTooLargeError(
            f"The response is larger than the {max_bytes:,} byte limit.",
            source=url,
        )
    try:
        return body.decode(encoding)
    except UnicodeDecodeError:
        raise MalformedJSONError(
            f"The response from {url!r} is not valid {encoding} text.",
            source=url,
        ) from None
