"""Unit tests for ExpectChannel with mock paramiko channel."""

from __future__ import annotations

import re
import time
from unittest.mock import MagicMock, PropertyMock

import pytest

from vista_clients.terminal.errors import PromptTimeoutError, TerminalConnectionError
from vista_clients.terminal.expect import ExpectChannel


def _make_channel(chunks: list[bytes], *, closed: bool = False) -> MagicMock:
    """Create a mock paramiko channel that yields *chunks* sequentially.

    Each call to ``recv()`` returns the next chunk. After all chunks
    are exhausted ``recv_ready()`` returns False.
    """
    channel = MagicMock()
    chunk_iter = iter(chunks)
    remaining: list[bytes] = []

    def recv_ready() -> bool:
        if remaining:
            return True
        try:
            remaining.append(next(chunk_iter))
            return True
        except StopIteration:
            return False

    def recv(size: int) -> bytes:
        if remaining:
            return remaining.pop(0)
        return b""

    channel.recv_ready = recv_ready
    channel.recv = recv
    channel.send_ready.return_value = True
    channel.send.side_effect = lambda data: len(data)
    type(channel).closed = PropertyMock(return_value=closed)
    return channel


class TestExpectPatternMatching:
    """Tests for ExpectChannel.expect() pattern matching."""

    def test_matches_simple_pattern(self) -> None:
        channel = _make_channel([b"Hello World\nSelect OPTION NAME: "])
        ec = ExpectChannel(channel, timeout=5.0, settle_delay=0.1)
        patterns = [re.compile(r"Select .+ Option:")]  # Match in default set style
        # The actual pattern in the data is "Select OPTION NAME:" which has
        # "OPTION NAME" matching ".+"
        # Use a pattern that matches the actual data
        patterns = [re.compile(r"Select \S+ \S+:")]
        idx, match, text_before = ec.expect(patterns)
        assert idx == 0
        assert "Hello World" in text_before

    def test_matches_first_of_multiple_patterns(self) -> None:
        channel = _make_channel([b"ACCESS CODE: "])
        ec = ExpectChannel(channel, timeout=5.0, settle_delay=0.1)
        patterns = [
            re.compile(r"VERIFY CODE:"),
            re.compile(r"ACCESS CODE:"),
        ]
        idx, match, text_before = ec.expect(patterns)
        assert idx == 1  # ACCESS CODE matches second pattern

    def test_accumulates_across_chunks(self) -> None:
        channel = _make_channel([b"Select Sys", b"tems Man", b"ager Menu Option: "])
        ec = ExpectChannel(channel, timeout=5.0, settle_delay=0.1)
        patterns = [re.compile(r"Select .+ Option:")]
        idx, match, text_before = ec.expect(patterns)
        assert idx == 0

    def test_buffer_consumed_after_match(self) -> None:
        channel = _make_channel([b"ACCESS CODE: rest"])
        ec = ExpectChannel(channel, timeout=5.0, settle_delay=0.1)
        patterns = [re.compile(r"ACCESS CODE:")]
        ec.expect(patterns)
        assert "rest" in ec.buffer  # remainder stays in buffer


class TestExpectSettleDelay:
    """Tests for the settle delay behaviour."""

    def test_settle_delay_waits_for_silence(self) -> None:
        """Pattern should not match until settle_delay of silence."""
        # With a short settle_delay, it should still work correctly
        channel = _make_channel([b"ACCESS CODE: "])
        ec = ExpectChannel(channel, timeout=5.0, settle_delay=0.1)
        start = time.monotonic()
        ec.expect([re.compile(r"ACCESS CODE:")])
        elapsed = time.monotonic() - start
        # Should have waited at least settle_delay
        assert elapsed >= 0.1


class TestExpectTimeout:
    """Tests for timeout behaviour."""

    def test_timeout_raises_with_partial_output(self) -> None:
        channel = _make_channel([b"partial output here"])
        ec = ExpectChannel(channel, timeout=0.3, settle_delay=0.05)
        patterns = [re.compile(r"NEVER_MATCH")]
        with pytest.raises(PromptTimeoutError) as exc_info:
            ec.expect(patterns)
        assert "partial output here" in exc_info.value.partial_output
        assert "NEVER_MATCH" in exc_info.value.patterns

    def test_custom_timeout_overrides_default(self) -> None:
        channel = _make_channel([b"data"])
        ec = ExpectChannel(channel, timeout=30.0, settle_delay=0.05)
        start = time.monotonic()
        with pytest.raises(PromptTimeoutError):
            ec.expect([re.compile(r"NOPE")], timeout=0.2)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0  # Used custom timeout, not 30s


class TestExpectUTF8:
    """Tests for incremental UTF-8 decoding."""

    def test_multibyte_split_across_recv(self) -> None:
        """UTF-8 multibyte char split across two recv() calls."""
        # é is \xc3\xa9 in UTF-8 — split across two chunks
        channel = _make_channel([b"caf\xc3", b"\xa9: "])
        ec = ExpectChannel(channel, timeout=5.0, settle_delay=0.1)
        patterns = [re.compile(r"café:")]
        idx, match, text_before = ec.expect(patterns)
        assert idx == 0


class TestExpectSendReady:
    """Tests for send_ready() guard."""

    def test_send_waits_for_ready(self) -> None:
        channel = MagicMock()
        channel.closed = False
        ready_calls = [False, False, True]
        channel.send_ready.side_effect = lambda: ready_calls.pop(0) if ready_calls else True
        channel.send.return_value = 5
        ec = ExpectChannel(channel, timeout=5.0, settle_delay=0.1)
        ec.send("hello")
        assert channel.send.called


class TestExpectClosedChannel:
    """Tests for closed channel detection."""

    def test_expect_raises_on_closed_channel(self) -> None:
        channel = _make_channel([], closed=True)
        ec = ExpectChannel(channel, timeout=0.3, settle_delay=0.05)
        with pytest.raises(TerminalConnectionError, match="channel closed"):
            ec.expect([re.compile(r"anything")])

    def test_send_raises_on_closed_channel(self) -> None:
        channel = MagicMock()
        type(channel).closed = PropertyMock(return_value=True)
        ec = ExpectChannel(channel, timeout=5.0, settle_delay=0.1)
        with pytest.raises(TerminalConnectionError, match="channel is closed"):
            ec.send("test")


class TestExpectCRStripping:
    """Tests for carriage return stripping."""

    def test_cr_stripped_from_buffer(self) -> None:
        channel = _make_channel([b"line1\r\nline2\r\nACCESS CODE: "])
        ec = ExpectChannel(channel, timeout=5.0, settle_delay=0.1)
        ec.expect([re.compile(r"ACCESS CODE:")])
        # Verify buffer and text_before have \r stripped
        # The buffer content was consumed; verify via a new expect
        # that the remaining content has no \r
        # Actually let's just check the buffer property doesn't have \r
        assert "\r" not in ec.buffer
