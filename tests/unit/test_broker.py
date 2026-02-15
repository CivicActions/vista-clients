"""Unit tests for VistABroker (mocked transport, no network).

T029: Credential resolution order
T054: Session state enforcement
T055: Handshake failure handling
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from vista_test.rpc.broker import _DEFAULT_ACCESS, _DEFAULT_VERIFY, VistABroker
from vista_test.rpc.errors import (
    HandshakeError,
    StateError,
)
from vista_test.rpc.protocol import CredentialSource, SessionState

# ---------------------------------------------------------------------------
# T029: Credential resolution order
# ---------------------------------------------------------------------------


class TestCredentialResolution:
    """Explicit overrides env, env overrides defaults."""

    def test_explicit_credentials(self):
        broker = VistABroker("localhost", 9430)
        ac, vc, source = broker._resolve_credentials("MYAC", "MYVC")
        assert ac == "MYAC"
        assert vc == "MYVC"
        assert source == CredentialSource.EXPLICIT

    def test_env_credentials(self):
        broker = VistABroker("localhost", 9430)
        with patch.dict(
            os.environ,
            {"VISTA_ACCESS_CODE": "ENVAC", "VISTA_VERIFY_CODE": "ENVVC"},
        ):
            ac, vc, source = broker._resolve_credentials(None, None)
        assert ac == "ENVAC"
        assert vc == "ENVVC"
        assert source == CredentialSource.ENVIRONMENT

    def test_default_credentials(self):
        broker = VistABroker("localhost", 9430)
        with patch.dict(
            os.environ,
            {"VISTA_ACCESS_CODE": "", "VISTA_VERIFY_CODE": ""},
            clear=False,
        ):
            # Also clear the env vars entirely
            os.environ.pop("VISTA_ACCESS_CODE", None)
            os.environ.pop("VISTA_VERIFY_CODE", None)
            ac, vc, source = broker._resolve_credentials(None, None)
        assert ac == _DEFAULT_ACCESS
        assert vc == _DEFAULT_VERIFY
        assert source == CredentialSource.DEFAULT

    def test_explicit_overrides_env(self):
        """Explicit params win even when env vars are set."""
        broker = VistABroker("localhost", 9430)
        with patch.dict(
            os.environ,
            {"VISTA_ACCESS_CODE": "ENVAC", "VISTA_VERIFY_CODE": "ENVVC"},
        ):
            ac, _vc, source = broker._resolve_credentials("MYAC", "MYVC")
        assert ac == "MYAC"
        assert source == CredentialSource.EXPLICIT

    def test_partial_explicit_falls_to_env(self):
        """If only one explicit param, fall through to env."""
        broker = VistABroker("localhost", 9430)
        with patch.dict(
            os.environ,
            {"VISTA_ACCESS_CODE": "ENVAC", "VISTA_VERIFY_CODE": "ENVVC"},
        ):
            ac, _vc, source = broker._resolve_credentials("MYAC", None)
        assert ac == "ENVAC"
        assert source == CredentialSource.ENVIRONMENT


# ---------------------------------------------------------------------------
# T054: Session state enforcement
# ---------------------------------------------------------------------------


class TestStateEnforcement:
    """StateError raised when operations are called in wrong state."""

    def test_authenticate_before_handshake(self):
        broker = VistABroker("localhost", 9430)
        # State is DISCONNECTED, need HANDSHAKED
        with pytest.raises(StateError):
            broker.authenticate()

    def test_create_context_before_auth(self):
        broker = VistABroker("localhost", 9430)
        # State is DISCONNECTED, need AUTHENTICATED or CONTEXT_SET
        with pytest.raises(StateError):
            broker.create_context("OR CPRS GUI CHART")

    def test_call_rpc_before_context(self):
        broker = VistABroker("localhost", 9430)
        # State is DISCONNECTED, need CONTEXT_SET
        with pytest.raises(StateError):
            broker.call_rpc("ORWU USERINFO")

    def test_connect_when_already_connected(self):
        broker = VistABroker("localhost", 9430)
        # Force state to HANDSHAKED without actual connection
        broker._state = SessionState.HANDSHAKED
        with pytest.raises(StateError):
            broker.connect()

    def test_ping_when_disconnected(self):
        broker = VistABroker("localhost", 9430)
        with pytest.raises(StateError):
            broker.ping()

    def test_create_context_in_handshaked_state(self):
        """Create context requires AUTHENTICATED or CONTEXT_SET, not HANDSHAKED."""
        broker = VistABroker("localhost", 9430)
        broker._state = SessionState.HANDSHAKED
        with pytest.raises(StateError):
            broker.create_context("OR CPRS GUI CHART")

    def test_call_rpc_in_authenticated_state(self):
        """call_rpc requires CONTEXT_SET, not just AUTHENTICATED."""
        broker = VistABroker("localhost", 9430)
        broker._state = SessionState.AUTHENTICATED
        with pytest.raises(StateError):
            broker.call_rpc("ORWU USERINFO")


# ---------------------------------------------------------------------------
# T055: Handshake failure
# ---------------------------------------------------------------------------


class TestHandshakeFailure:
    """Verify HandshakeError raised when server rejects connection."""

    @patch("vista_test.rpc.broker.Transport")
    def test_rejection_response_raises_handshake_error(self, MockTransport):
        """Server returns non-'accept' response."""
        mock_transport = MagicMock()
        mock_transport.is_connected = True
        mock_transport.receive.return_value = "reject"
        MockTransport.return_value = mock_transport

        broker = VistABroker("localhost", 9430)
        with pytest.raises(HandshakeError, match="rejected"):
            broker.connect()

    @patch("vista_test.rpc.broker.Transport")
    def test_transport_error_during_handshake(self, MockTransport):
        """Transport exception during handshake raises HandshakeError."""
        mock_transport = MagicMock()
        mock_transport.is_connected = True
        mock_transport.send.side_effect = [None, Exception("broken pipe")]
        mock_transport.receive.return_value = "accept"
        MockTransport.return_value = mock_transport

        broker = VistABroker("localhost", 9430)
        # First send succeeds (though won't hit second in actual flow)
        # The send for the handshake should fail
        # Actually connect() sends TCPConnect only once after TCP connect
        # Let's make the first send fail
        mock_transport.send.side_effect = Exception("broken pipe")
        with pytest.raises(HandshakeError, match="broken pipe"):
            broker.connect()

    def test_constructor_invalid_port(self):
        with pytest.raises(ValueError, match="port"):
            VistABroker("localhost", 0)
        with pytest.raises(ValueError, match="port"):
            VistABroker("localhost", 70000)

    def test_constructor_invalid_timeout(self):
        with pytest.raises(ValueError, match="timeout"):
            VistABroker("localhost", timeout=0)
        with pytest.raises(ValueError, match="timeout"):
            VistABroker("localhost", timeout=-1)
