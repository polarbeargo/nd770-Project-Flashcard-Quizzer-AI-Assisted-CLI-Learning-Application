"""Tests for the HTTP(S) fetcher using an injected fake opener (no network)."""

from __future__ import annotations

import io
import socket
import urllib.error
from email.message import Message

import pytest

from flashcards.exceptions import (
    FileTooLargeError,
    MalformedJSONError,
    RemoteFetchError,
)
from flashcards.remote import USER_AGENT, fetch_text, validate_url


class FakeResponse:
    def __init__(self, body: bytes, headers: dict | None = None) -> None:
        self._stream = io.BytesIO(body)
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._stream.close()


def opener_returning(body: bytes, headers: dict | None = None):
    captured = {}

    def _open(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(body, headers)

    return _open, captured


def opener_raising(error: Exception):
    def _open(request, timeout):
        raise error

    return _open


class TestValidateUrl:
    def test_accepts_http_and_https(self):
        assert (
            validate_url(" https://example.com/d.json ") == "https://example.com/d.json"
        )
        assert validate_url("HTTP://example.com") == "HTTP://example.com"

    @pytest.mark.parametrize(
        "url", ["ftp://x/y", "file:///etc/passwd", "example.com/x", ""]
    )
    def test_rejects_other_schemes_or_relative(self, url):
        with pytest.raises(RemoteFetchError):
            validate_url(url)

    def test_rejects_missing_host(self):
        with pytest.raises(RemoteFetchError, match="no host"):
            validate_url("http:///path-only")

    def test_rejects_non_string(self):
        with pytest.raises(RemoteFetchError, match="empty"):
            validate_url(None)  # type: ignore[arg-type]


class TestFetchText:
    def test_success_sets_headers_and_timeout(self):
        opener, captured = opener_returning(b'[{"front":"Q","back":"A"}]')
        text = fetch_text("https://example.com/d.json", timeout=4.5, opener=opener)
        assert text.startswith("[")
        assert captured["timeout"] == 4.5
        request = captured["request"]
        assert request.get_header("User-agent") == USER_AGENT
        assert request.get_header("Accept") == "application/json"

    def test_declared_content_length_over_limit(self):
        opener, _ = opener_returning(b"[]", {"Content-Length": "5000"})
        with pytest.raises(FileTooLargeError, match="server reports 5,000 bytes"):
            fetch_text("https://example.com", max_bytes=100, opener=opener)

    def test_actual_body_over_limit(self):
        opener, _ = opener_returning(b"x" * 50)
        with pytest.raises(FileTooLargeError, match="larger than the 10 byte limit"):
            fetch_text("https://example.com", max_bytes=10, opener=opener)

    def test_non_numeric_content_length_is_ignored(self):
        opener, _ = opener_returning(b"[]", {"Content-Length": "abc"})
        assert fetch_text("https://example.com", opener=opener) == "[]"

    def test_http_error(self):
        error = urllib.error.HTTPError("https://e", 404, "Not Found", Message(), None)
        with pytest.raises(RemoteFetchError, match="HTTP 404 Not Found"):
            fetch_text("https://example.com", opener=opener_raising(error))

    def test_url_error_generic(self):
        error = urllib.error.URLError("name resolution failed")
        with pytest.raises(RemoteFetchError, match="Could not reach"):
            fetch_text("https://example.com", opener=opener_raising(error))

    def test_url_error_wrapping_timeout(self):
        error = urllib.error.URLError(socket.timeout("timed out"))
        with pytest.raises(RemoteFetchError, match="Timed out"):
            fetch_text("https://example.com", opener=opener_raising(error))

    def test_bare_timeout(self):
        with pytest.raises(RemoteFetchError, match="Timed out"):
            fetch_text("https://example.com", opener=opener_raising(TimeoutError()))

    def test_other_os_error(self):
        with pytest.raises(RemoteFetchError, match="Network error"):
            fetch_text(
                "https://example.com",
                opener=opener_raising(ConnectionResetError("rst")),
            )

    def test_invalid_encoding_in_body(self):
        opener, _ = opener_returning(b"\xff\xfe")
        with pytest.raises(MalformedJSONError, match="not valid utf-8"):
            fetch_text("https://example.com", opener=opener)


class TestBoundaries:
    def test_body_exactly_at_limit_is_accepted(self):
        opener, _ = opener_returning(b"[]")
        assert fetch_text("https://example.com", max_bytes=2, opener=opener) == "[]"

    def test_declared_length_exactly_at_limit_is_accepted(self):
        opener, _ = opener_returning(b"[]", {"Content-Length": "2"})
        assert fetch_text("https://example.com", max_bytes=2, opener=opener) == "[]"

    def test_size_errors_carry_url_as_source(self):
        opener, _ = opener_returning(b"xxx", {"Content-Length": "3"})
        with pytest.raises(FileTooLargeError) as info:
            fetch_text("https://example.com/d", max_bytes=2, opener=opener)
        assert info.value.source == "https://example.com/d"

    def test_injected_opener_is_called_exactly_once(self):
        opener, captured = opener_returning(b"[]")
        fetch_text("https://example.com", opener=opener)
        assert "request" in captured

    def test_body_over_limit_error_names_the_url(self):
        opener, _ = opener_returning(b"xxxx")
        with pytest.raises(FileTooLargeError) as info:
            fetch_text("https://example.com/d", max_bytes=2, opener=opener)
        assert info.value.source == "https://example.com/d"

    def test_bad_encoding_error_names_the_url(self):
        opener, _ = opener_returning(b"\xff")
        with pytest.raises(MalformedJSONError) as info:
            fetch_text("https://example.com/d", opener=opener)
        assert info.value.source == "https://example.com/d"
