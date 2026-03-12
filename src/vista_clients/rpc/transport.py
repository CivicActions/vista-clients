"""TCP socket wrapper with XWB framing.

Handles low-level socket operations: connect, send, receive with
``chr(4)`` (EOT) framing, and close.
"""

from __future__ import annotations

import socket

from vista_clients.rpc.errors import BrokerConnectionError

# End-of-transmission marker
_EOT = chr(4)
_EOT_BYTE = b"\x04"
_RECV_SIZE = 4096


class Transport:
    """TCP socket wrapper with XWB framing.

    Args:
        host: IP address or hostname of the VistA server.
        port: TCP port of the RPC Broker listener.
        timeout: Connection and read timeout in seconds.
    """

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._sock: socket.socket | None = None

    @property
    def is_connected(self) -> bool:
        """Whether the TCP socket is currently open."""
        return self._sock is not None

    def connect(self) -> None:
        """Open TCP connection to the server.

        Raises:
            BrokerConnectionError: If the connection fails or times out.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._timeout)
            sock.connect((self._host, self._port))
            self._sock = sock
        except TimeoutError as exc:
            raise BrokerConnectionError(
                f"Connection timed out to {self._host}:{self._port}"
            ) from exc
        except OSError as exc:
            raise BrokerConnectionError(
                f"Connection refused to {self._host}:{self._port}: {exc}"
            ) from exc

    def send(self, data: bytes) -> None:
        """Send data over the TCP connection.

        Args:
            data: Raw bytes to send.

        Raises:
            BrokerConnectionError: If the socket is closed or send fails.
        """
        if self._sock is None:
            raise BrokerConnectionError("Not connected")
        try:
            self._sock.sendall(data)
        except OSError as exc:
            self._sock = None
            raise BrokerConnectionError(f"Send failed: {exc}") from exc

    def receive(self) -> str:
        """Read data from the socket until ``chr(4)`` (EOT) terminator.

        Strips the ``\\x00\\x00`` null prefix if present and the
        trailing EOT marker.

        Returns:
            Decoded response string.

        Raises:
            BrokerConnectionError: If the socket is closed, times out,
                or the remote end disconnects.
        """
        if self._sock is None:
            raise BrokerConnectionError("Not connected")

        chunks: list[bytes] = []
        try:
            while True:
                chunk = self._sock.recv(_RECV_SIZE)
                if not chunk:
                    raise BrokerConnectionError("Connection closed by server")
                if _EOT_BYTE in chunk:
                    # Take everything before EOT
                    idx = chunk.index(_EOT_BYTE)
                    chunks.append(chunk[:idx])
                    break
                chunks.append(chunk)
        except TimeoutError as exc:
            raise BrokerConnectionError("Receive timed out") from exc
        except OSError as exc:
            self._sock = None
            raise BrokerConnectionError(f"Receive failed: {exc}") from exc

        raw = b"".join(chunks)
        text = raw.decode("utf-8", errors="replace")

        # Strip \x00\x00 null prefix (from XWBRW.m)
        if text.startswith("\x00\x00"):
            text = text[2:]

        return text

    def close(self) -> None:
        """Close the TCP socket.

        Safe to call multiple times. No-op if already closed.
        """
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
