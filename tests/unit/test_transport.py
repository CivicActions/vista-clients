"""Unit tests for Transport using mock sockets."""

from unittest.mock import MagicMock, patch

import pytest

from vista_test.rpc.errors import ConnectionError
from vista_test.rpc.transport import Transport


class TestTransportConnect:
    def test_connect_success(self):
        with patch("vista_test.rpc.transport.socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_cls.return_value = mock_sock

            t = Transport("localhost", 9430, 30.0)
            t.connect()

            mock_sock.settimeout.assert_called_once_with(30.0)
            mock_sock.connect.assert_called_once_with(("localhost", 9430))
            assert t.is_connected

    def test_connect_timeout_raises_connection_error(self):
        with patch("vista_test.rpc.transport.socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = TimeoutError("timed out")
            mock_cls.return_value = mock_sock

            t = Transport("localhost", 9430, 1.0)
            with pytest.raises(ConnectionError, match="timed out"):
                t.connect()
            assert not t.is_connected

    def test_connect_refused_raises_connection_error(self):
        with patch("vista_test.rpc.transport.socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = OSError("Connection refused")
            mock_cls.return_value = mock_sock

            t = Transport("localhost", 9999, 5.0)
            with pytest.raises(ConnectionError, match="refused"):
                t.connect()
            assert not t.is_connected


class TestTransportSend:
    def _connected_transport(self):
        t = Transport("localhost", 9430, 30.0)
        t._sock = MagicMock()
        return t

    def test_send_data(self):
        t = self._connected_transport()
        t.send(b"hello")
        t._sock.sendall.assert_called_once_with(b"hello")

    def test_send_not_connected_raises(self):
        t = Transport("localhost", 9430, 30.0)
        with pytest.raises(ConnectionError, match="Not connected"):
            t.send(b"data")

    def test_send_broken_connection_raises(self):
        t = self._connected_transport()
        t._sock.sendall.side_effect = OSError("Broken pipe")
        with pytest.raises(ConnectionError, match="Send failed"):
            t.send(b"data")
        assert not t.is_connected


class TestTransportReceive:
    def _connected_transport(self):
        t = Transport("localhost", 9430, 30.0)
        t._sock = MagicMock()
        return t

    def test_receive_single_chunk_with_eot(self):
        t = self._connected_transport()
        t._sock.recv.return_value = b"accept\x04"

        result = t.receive()
        assert result == "accept"

    def test_receive_strips_null_prefix(self):
        t = self._connected_transport()
        t._sock.recv.return_value = b"\x00\x00some data\x04"

        result = t.receive()
        assert result == "some data"

    def test_receive_multi_chunk(self):
        """TCP fragment reassembly: data arrives in multiple chunks."""
        t = self._connected_transport()
        t._sock.recv.side_effect = [
            b"hel",
            b"lo wor",
            b"ld\x04",
        ]
        result = t.receive()
        assert result == "hello world"

    def test_receive_eot_in_middle_of_chunk(self):
        """EOT marker not at end of chunk — take only data before it."""
        t = self._connected_transport()
        t._sock.recv.return_value = b"data\x04trailing"

        result = t.receive()
        assert result == "data"

    def test_receive_not_connected_raises(self):
        t = Transport("localhost", 9430, 30.0)
        with pytest.raises(ConnectionError, match="Not connected"):
            t.receive()

    def test_receive_timeout_raises(self):
        t = self._connected_transport()
        t._sock.recv.side_effect = TimeoutError("timed out")
        with pytest.raises(ConnectionError, match="Receive timed out"):
            t.receive()

    def test_receive_connection_closed_by_server(self):
        """Server closes connection — recv returns empty bytes."""
        t = self._connected_transport()
        t._sock.recv.return_value = b""
        with pytest.raises(ConnectionError, match="closed by server"):
            t.receive()

    def test_receive_mid_receive_drop(self):
        """Connection drops after partial data received."""
        t = self._connected_transport()
        t._sock.recv.side_effect = [
            b"partial",
            OSError("Connection reset by peer"),
        ]
        with pytest.raises(ConnectionError, match="Receive failed"):
            t.receive()
        assert not t.is_connected


class TestTransportClose:
    def test_close_connected(self):
        t = Transport("localhost", 9430, 30.0)
        mock_sock = MagicMock()
        t._sock = mock_sock
        t.close()
        mock_sock.close.assert_called_once()
        assert not t.is_connected

    def test_close_already_closed_noop(self):
        t = Transport("localhost", 9430, 30.0)
        t.close()  # Should not raise
        assert not t.is_connected

    def test_close_error_suppressed(self):
        t = Transport("localhost", 9430, 30.0)
        t._sock = MagicMock()
        t._sock.close.side_effect = OSError("socket error")
        t.close()  # Should not raise
        assert not t.is_connected
