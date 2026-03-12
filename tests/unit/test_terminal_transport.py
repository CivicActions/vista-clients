"""Unit tests for SSHTransport with mocked paramiko."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vista_clients.terminal.errors import AuthenticationError, TerminalConnectionError
from vista_clients.terminal.transport import SSHTransport


@pytest.fixture()
def mock_ssh_client() -> MagicMock:
    """Create a mock paramiko.SSHClient."""
    client = MagicMock()
    transport = MagicMock()
    transport.is_active.return_value = True
    client.get_transport.return_value = transport
    channel = MagicMock()
    channel.closed = False
    client.invoke_shell.return_value = channel
    return client


class TestSSHTransportConnect:
    """Tests for SSHTransport.connect()."""

    @patch("vista_clients.terminal.transport.paramiko.SSHClient")
    def test_connect_success(self, mock_cls: MagicMock) -> None:
        mock_client = mock_cls.return_value
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_channel = MagicMock()
        mock_channel.closed = False
        mock_client.invoke_shell.return_value = mock_channel

        t = SSHTransport("localhost", 2222, 30.0)
        t.connect("user", "pass")

        mock_client.set_missing_host_key_policy.assert_called_once()
        mock_client.connect.assert_called_once_with(
            hostname="localhost",
            port=2222,
            username="user",
            password="pass",
            timeout=30.0,
            allow_agent=False,
            look_for_keys=False,
        )
        mock_client.invoke_shell.assert_called_once_with(term="vt100")
        assert t.is_connected is True

    @patch("vista_clients.terminal.transport.paramiko.SSHClient")
    def test_connect_auth_failure(self, mock_cls: MagicMock) -> None:
        import paramiko as _paramiko

        mock_client = mock_cls.return_value
        mock_client.connect.side_effect = _paramiko.AuthenticationException("bad")

        t = SSHTransport("localhost", 2222, 30.0)
        with pytest.raises(AuthenticationError, match="SSH authentication failed") as exc_info:
            t.connect("user", "wrongpass")
        assert exc_info.value.level == "ssh"

    @patch("vista_clients.terminal.transport.paramiko.SSHClient")
    def test_connect_network_failure(self, mock_cls: MagicMock) -> None:
        mock_client = mock_cls.return_value
        mock_client.connect.side_effect = OSError("Connection refused")

        t = SSHTransport("badhost", 2222, 5.0)
        with pytest.raises(TerminalConnectionError, match="SSH connection.*failed"):
            t.connect("user", "pass")


class TestSSHTransportState:
    """Tests for is_connected and close."""

    def test_not_connected_initially(self) -> None:
        t = SSHTransport("localhost", 2222, 30.0)
        assert t.is_connected is False

    @patch("vista_clients.terminal.transport.paramiko.SSHClient")
    def test_close_disconnects(self, mock_cls: MagicMock) -> None:
        mock_client = mock_cls.return_value
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_channel = MagicMock()
        mock_channel.closed = False
        mock_client.invoke_shell.return_value = mock_channel

        t = SSHTransport("localhost", 2222, 30.0)
        t.connect("user", "pass")
        assert t.is_connected is True

        t.close()
        assert t.is_connected is False

    @patch("vista_clients.terminal.transport.paramiko.SSHClient")
    def test_close_idempotent(self, mock_cls: MagicMock) -> None:
        mock_client = mock_cls.return_value
        mock_client.invoke_shell.return_value = MagicMock(closed=False)
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport

        t = SSHTransport("localhost", 2222, 30.0)
        t.connect("user", "pass")
        t.close()
        t.close()  # second call should not raise
        assert t.is_connected is False

    def test_channel_property_raises_when_disconnected(self) -> None:
        t = SSHTransport("localhost", 2222, 30.0)
        with pytest.raises(TerminalConnectionError, match="Not connected"):
            _ = t.channel
