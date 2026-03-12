"""Expect-style prompt matching engine over a paramiko channel.

Provides ``ExpectChannel``, a custom pexpect-like interface that
reads from a ``paramiko.Channel``, accumulates output, and matches
against a list of compiled regex patterns after observing a
configurable settling delay (no new data for *settle_delay* seconds).
"""

from __future__ import annotations

import codecs
import logging
import re
import time
from typing import TYPE_CHECKING

from vista_clients.terminal.errors import PromptTimeoutError, TerminalConnectionError

if TYPE_CHECKING:
    import paramiko

logger = logging.getLogger(__name__)

# Chunk size for ``channel.recv()``
_RECV_SIZE = 4096

# Poll interval (seconds) for the ``recv_ready()`` loop
_POLL_INTERVAL = 0.05


class ExpectChannel:
    """pexpect-style interface over a paramiko Channel.

    Reads data from the channel, decodes incrementally (UTF-8),
    strips carriage returns, and matches prompt patterns after a
    quiet "settle" period.

    Args:
        channel: An open ``paramiko.Channel`` with an interactive shell.
        timeout: Default seconds to wait for a prompt match.
        settle_delay: Seconds of silence required before evaluating
            prompt patterns against the buffer.
    """

    def __init__(
        self,
        channel: paramiko.Channel,
        timeout: float = 30.0,
        settle_delay: float = 0.5,
    ) -> None:
        self._channel = channel
        self._timeout = timeout
        self._settle_delay = settle_delay
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._buffer = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def expect(
        self,
        patterns: list[re.Pattern[str]],
        timeout: float | None = None,
    ) -> tuple[int, re.Match[str], str]:
        """Block until one of *patterns* matches after the settle period.

        Continually reads from the channel and checks whether any of
        the patterns match the accumulated buffer.  A match is only
        accepted after *settle_delay* seconds of no new data, ensuring
        that VistA's bursty output has finished arriving.

        Args:
            patterns: Compiled regex patterns to match against.
            timeout: Override the default timeout for this call.

        Returns:
            A tuple ``(index, match, text_before)`` where *index* is
            the position in *patterns* that matched, *match* is the
            ``re.Match`` object, and *text_before* is the buffer
            content preceding the match.

        Raises:
            PromptTimeoutError: If no pattern matches within *timeout*.
            TerminalConnectionError: If the channel is closed during reading.
        """
        effective_timeout = timeout if timeout is not None else self._timeout
        deadline = time.monotonic() + effective_timeout
        last_data_time = time.monotonic()

        while True:
            now = time.monotonic()
            if now >= deadline:
                self._raise_timeout(patterns)

            # Read any available data
            data_received = self._read_available()
            if data_received:
                last_data_time = time.monotonic()

            # Only evaluate patterns after the settle delay
            elapsed_since_data = time.monotonic() - last_data_time
            if elapsed_since_data >= self._settle_delay and self._buffer:
                result = self._try_match(patterns)
                if result is not None:
                    return result

            # Check for closed channel
            if self._channel.closed:
                raise TerminalConnectionError("SSH channel closed while waiting for prompt")

            # Small sleep to avoid busy-waiting
            time.sleep(min(_POLL_INTERVAL, max(0, deadline - time.monotonic())))

    def send(self, text: str) -> None:
        """Send raw text to the channel.

        Waits for ``send_ready()`` before sending to avoid blocking
        on a full send buffer.

        Args:
            text: The text to send.

        Raises:
            TerminalConnectionError: If the channel is closed.
        """
        if self._channel.closed:
            raise TerminalConnectionError("SSH channel is closed")
        data = text.encode("utf-8")
        while data:
            if not self._channel.send_ready():
                time.sleep(_POLL_INTERVAL)
                continue
            sent = self._channel.send(data)
            data = data[sent:]
        logger.debug("Sent: %r", text)

    def sendline(self, text: str = "") -> None:
        """Send text followed by a carriage return (``\\r``).

        Args:
            text: The text to send before the CR.
        """
        self.send(text + "\r")

    @property
    def buffer(self) -> str:
        """Current accumulated unprocessed output."""
        return self._buffer

    def clear_buffer(self) -> None:
        """Clear the accumulated buffer."""
        self._buffer = ""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_available(self) -> bool:
        """Read all available data from the channel into the buffer.

        Returns:
            ``True`` if any data was read, ``False`` otherwise.
        """
        got_data = False
        while self._channel.recv_ready():
            try:
                raw = self._channel.recv(_RECV_SIZE)
            except Exception as exc:
                raise TerminalConnectionError(f"Error reading from SSH channel: {exc}") from exc
            if not raw:
                break
            decoded = self._decoder.decode(raw)
            # Strip carriage returns (pty delivers \r\n)
            decoded = decoded.replace("\r", "")
            logger.debug("Recv: %r", decoded)
            self._buffer += decoded
            got_data = True
        return got_data

    def _try_match(
        self,
        patterns: list[re.Pattern[str]],
    ) -> tuple[int, re.Match[str], str] | None:
        """Try to match any pattern against the current buffer.

        Returns the match result tuple or ``None`` if nothing matched.
        """
        for idx, pattern in enumerate(patterns):
            m = pattern.search(self._buffer)
            if m:
                text_before = self._buffer[: m.start()]
                # Consume matched content from buffer
                self._buffer = self._buffer[m.end() :]
                return idx, m, text_before
        return None

    def _raise_timeout(self, patterns: list[re.Pattern[str]]) -> None:
        """Raise ``PromptTimeoutError`` with current buffer state."""
        pattern_strs = [p.pattern for p in patterns]
        raise PromptTimeoutError(
            f"Prompt not detected within timeout. "
            f"Patterns: {pattern_strs}. "
            f"Buffer tail: {self._buffer[-200:]!r}",
            partial_output=self._buffer,
            patterns=pattern_strs,
        )
