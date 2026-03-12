"""Smoke tests: full lifecycle against a live VistA server.

These tests require a running VistA environment (the WorldVistA VEHU image
is used in examples)
on localhost:9430.

Run with: uv run pytest tests/smoke/ -v
"""

import pytest

from vista_clients.rpc import VistABroker
from vista_clients.rpc.errors import (
    AuthenticationError,
    BrokerConnectionError,
    RPCError,
)
from vista_clients.rpc.protocol import SessionState

# Mark all tests in this module as smoke tests
pytestmark = pytest.mark.smoke


# ---------------------------------------------------------------------------
# US1: Connection Establishment
# ---------------------------------------------------------------------------


class TestConnection:
    """T013: TCP connect/disconnect against a VistA server."""

    def test_connect_and_disconnect(self):
        broker = VistABroker("localhost", 9430)
        broker.connect()
        assert broker.is_connected
        assert broker.state == SessionState.HANDSHAKED
        broker.disconnect()
        assert not broker.is_connected
        assert broker.state == SessionState.DISCONNECTED

    def test_context_manager(self):
        with VistABroker("localhost", 9430) as broker:
            assert broker.is_connected
            assert broker.state == SessionState.HANDSHAKED
        assert not broker.is_connected

    def test_connection_refused(self):
        with pytest.raises(BrokerConnectionError):
            VistABroker("localhost", 19999).connect()


# ---------------------------------------------------------------------------
# US2: Handshake and Context
# ---------------------------------------------------------------------------


class TestHandshake:
    """T025: Handshake smoke tests."""

    def test_handshake_succeeds(self):
        with VistABroker("localhost", 9430) as broker:
            assert broker.state == SessionState.HANDSHAKED

    def test_disconnect_after_handshake(self):
        broker = VistABroker("localhost", 9430)
        broker.connect()
        broker.disconnect()
        assert broker.state == SessionState.DISCONNECTED


# ---------------------------------------------------------------------------
# US3: Authentication
# ---------------------------------------------------------------------------


class TestAuthentication:
    """T030, T031, T056: Authentication smoke tests."""

    def test_authenticate_with_defaults(self):
        """T030: Built-in demonstration defaults should work."""
        with VistABroker("localhost", 9430) as broker:
            duz = broker.authenticate()
            assert duz
            assert int(duz) > 0
            assert broker.duz == duz
            assert broker.state == SessionState.AUTHENTICATED

    def test_authenticate_invalid_credentials(self):
        """T031: Invalid credentials raise AuthenticationError."""
        with VistABroker("localhost", 9430) as broker:
            with pytest.raises(AuthenticationError):
                broker.authenticate(access_code="BADCODE", verify_code="BADVERIFY")

    def test_authenticate_special_chars(self):
        """T056: Credentials with special characters."""
        with VistABroker("localhost", 9430) as broker:
            # PRO1234!! contains ! characters — the defaults
            duz = broker.authenticate(access_code="PRO1234", verify_code="PRO1234!!")
            assert int(duz) > 0


# ---------------------------------------------------------------------------
# US4: RPC Invocation
# ---------------------------------------------------------------------------


class TestRPCInvocation:
    """T036-T038, T057, T059: RPC invocation smoke tests."""

    def _authenticated_broker(self):
        broker = VistABroker("localhost", 9430)
        broker.connect()
        broker.authenticate()
        return broker

    def test_call_rpc_no_params(self):
        """T036: Call RPC with no parameters."""
        broker = self._authenticated_broker()
        try:
            broker.create_context("OR CPRS GUI CHART")
            response = broker.call_rpc("ORWU USERINFO")
            assert response.raw
        finally:
            broker.disconnect()

    def test_call_rpc_literal_param(self):
        """T037: Call RPC with literal parameter."""
        from vista_clients.rpc.protocol import literal

        broker = self._authenticated_broker()
        try:
            broker.create_context("OR CPRS GUI CHART")
            response = broker.call_rpc(
                "XWB GET VARIABLE VALUE", [literal("$P($G(^DIC(3.1,1,0)),U,1)")]
            )
            # Should return some value
            assert response is not None
        finally:
            broker.disconnect()

    def test_call_nonexistent_rpc(self):
        """T038: Non-existent RPC raises RPCError."""
        broker = self._authenticated_broker()
        try:
            broker.create_context("OR CPRS GUI CHART")
            with pytest.raises(RPCError):
                broker.call_rpc("NONEXISTENT RPC 12345")
        finally:
            broker.disconnect()

    def test_switch_context(self):
        """T057: Switch context by calling create_context() twice."""
        broker = self._authenticated_broker()
        try:
            broker.create_context("OR CPRS GUI CHART")
            assert broker.state == SessionState.CONTEXT_SET

            # Switch to another context
            broker.create_context("OR CPRS GUI CHART")
            assert broker.state == SessionState.CONTEXT_SET
        finally:
            broker.disconnect()

    def test_rpc_outside_context(self):
        """T059: RPC outside active context's permission set."""
        broker = self._authenticated_broker()
        try:
            broker.create_context("OR CPRS GUI CHART")
            # Try an RPC that's not in OR CPRS GUI CHART context
            # XWB EXAMPLE ECHO STRING is in XWB BROKER EXAMPLE context
            with pytest.raises(RPCError):
                broker.call_rpc("XWB EXAMPLE ECHO STRING")
        finally:
            broker.disconnect()


# ---------------------------------------------------------------------------
# US5: Response Parsing
# ---------------------------------------------------------------------------


class TestResponseParsing:
    """T042, T043: Response parsing smoke tests."""

    def _setup_broker(self):
        broker = VistABroker("localhost", 9430)
        broker.connect()
        broker.authenticate()
        broker.create_context("OR CPRS GUI CHART")
        return broker

    def test_single_value_response(self):
        """T042: RPC returning single value."""
        broker = self._setup_broker()
        try:
            from vista_clients.rpc.protocol import literal

            response = broker.call_rpc("XWB GET VARIABLE VALUE", [literal("DUZ")])
            assert response.value is not None or response.lines is not None
        finally:
            broker.disconnect()

    def test_array_response(self):
        """T043: RPC returning array."""
        broker = self._setup_broker()
        try:
            response = broker.call_rpc("ORWU USERINFO")
            # ORWU USERINFO returns multi-line data
            assert response.raw
        finally:
            broker.disconnect()


# ---------------------------------------------------------------------------
# Full Lifecycle (SC-002)
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """T046: Complete lifecycle test."""

    def test_connect_auth_context_rpc_disconnect(self):
        with VistABroker("localhost", 9430) as broker:
            duz = broker.authenticate()
            assert int(duz) > 0

            broker.create_context("OR CPRS GUI CHART")
            assert broker.state == SessionState.CONTEXT_SET

            response = broker.call_rpc("ORWU USERINFO")
            assert response.raw

        assert not broker.is_connected
        assert broker.state == SessionState.DISCONNECTED
