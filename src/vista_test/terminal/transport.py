"""SSH transport wrapper for interactive VistA terminal sessions.

Provides ``SSHTransport``, a thin wrapper around ``paramiko.SSHClient``
that establishes an interactive shell channel with a VT100 pty.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import paramiko

from vista_test.terminal.errors import AuthenticationError, ConnectionError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SSHTransport:
    """Paramiko SSH wrapper for interactive terminal sessions.

    Manages the lifecycle of an SSH connection and its interactive
    shell channel.

    Args:
        host: IP address or hostname of the SSH server.
        port: SSH port number.
        timeout: Connection timeout in seconds.
    """

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._client: paramiko.SSHClient | None = None
        self._channel: paramiko.Channel | None = None

    def connect(
        self,
        username: str,
        password: str,
        terminal_type: str = "vt100",
    ) -> None:
        """Establish SSH connection, authenticate, and open interactive shell.

        Args:
            username: SSH username.
            password: SSH password.
            terminal_type: Terminal type for the pty (default ``"vt100"``).

        Raises:
            ConnectionError: If the SSH connection fails or times out.
            AuthenticationError: If OS-level password is rejected.
        """
        logger.info(
            "Connecting to %s:%d as %s",
            self._host,
            self._port,
            username,
        )
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self._host,
                port=self._port,
                username=username,
                password=password,
                timeout=self._timeout,
                allow_agent=False,
                look_for_keys=False,
            )
        except paramiko.AuthenticationException as exc:
            client.close()
            raise AuthenticationError(
                f"SSH authentication failed for user '{username}' "
                f"on {self._host}:{self._port}: {exc}",
                level="ssh",
            ) from exc
        except Exception as exc:
            client.close()
            raise ConnectionError(
                f"SSH connection to {self._host}:{self._port} failed: {exc}",
            ) from exc

        try:
            channel = client.invoke_shell(term=terminal_type)
            channel.settimeout(None)  # Non-blocking handled by expect engine
        except Exception as exc:
            client.close()
            raise ConnectionError(
                f"Failed to open interactive shell on {self._host}:{self._port}: {exc}",
            ) from exc

        self._client = client
        self._channel = channel
        logger.info("SSH connection established to %s:%d", self._host, self._port)

    @property
    def channel(self) -> paramiko.Channel:
        """The interactive shell channel.

        Raises:
            ConnectionError: If not connected.
        """
        if self._channel is None:
            raise ConnectionError("Not connected — no channel available")
        return self._channel

    @property
    def is_connected(self) -> bool:
        """Whether the SSH channel is open and active."""
        if self._channel is None or self._client is None:
            return False
        transport = self._client.get_transport()
        if transport is None or not transport.is_active():
            return False
        return not self._channel.closed

    def close(self) -> None:
        """Close the SSH channel and transport.

        Safe to call multiple times.  No-op if already closed.
        """
        if self._channel is not None:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        logger.info("SSH connection closed")
