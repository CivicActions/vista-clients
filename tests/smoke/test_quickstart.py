"""T047: Validate quickstart.md code examples execute against VEHU.

SC-001: The basic usage example should work in 10 lines or fewer.
"""

import pytest

from vista_test.rpc import VistABroker, literal

pytestmark = pytest.mark.smoke


class TestQuickstart:
    """Quickstart.md examples should work against live VEHU."""

    def test_basic_usage_10_lines(self):
        """SC-001: Connect, authenticate, context, RPC in ≤10 lines."""
        with VistABroker("localhost", 9430) as broker:
            duz = broker.authenticate()
            assert int(duz) > 0
            broker.create_context("OR CPRS GUI CHART")
            response = broker.call_rpc("ORWU USERINFO")
            assert response.raw

    def test_rpc_with_literal_param(self):
        """Quickstart example: call RPC with literal parameter."""
        with VistABroker("localhost", 9430) as broker:
            broker.authenticate()
            broker.create_context("OR CPRS GUI CHART")
            response = broker.call_rpc("XWB GET VARIABLE VALUE", [literal("DUZ")])
            assert response is not None

    def test_custom_credentials(self):
        """Quickstart example: explicit credentials."""
        with VistABroker("localhost", 9430) as broker:
            duz = broker.authenticate(access_code="PRO1234", verify_code="PRO1234!!")
            assert int(duz) > 0

    def test_error_handling_pattern(self):
        """Quickstart example: error handling with specific exceptions."""
        from vista_test.rpc.errors import (
            AuthenticationError,
            ConnectionError,
            ContextError,
            RPCError,
        )

        # Valid flow should not raise
        try:
            with VistABroker("localhost", 9430) as broker:
                broker.authenticate()
                broker.create_context("OR CPRS GUI CHART")
                response = broker.call_rpc("ORWU USERINFO")
                assert response.raw
        except (ConnectionError, AuthenticationError, ContextError, RPCError):
            pytest.fail("Basic quickstart flow should not raise")

    def test_keepalive_ping(self):
        """Quickstart example: ping to reset server timeout."""
        with VistABroker("localhost", 9430) as broker:
            broker.authenticate()
            broker.create_context("OR CPRS GUI CHART")
            # Ping should not raise
            broker.ping()
            # Should still be able to call RPC after ping
            response = broker.call_rpc("ORWU USERINFO")
            assert response.raw


class TestTerminalQuickstart:
    """Terminal quickstart.md examples should work against live VEHU."""

    def test_basic_terminal_usage_under_15_lines(self) -> None:
        """SC-001: Basic terminal usage in under 15 lines."""
        from vista_test.terminal import VistATerminal

        with VistATerminal("localhost", 2222) as term:
            term.login()
            output = term.send_and_wait("")
            assert isinstance(output, str)

    def test_explicit_connection_steps(self) -> None:
        """Quickstart example: explicit connect/login/disconnect."""
        from vista_test.terminal import VistATerminal

        term = VistATerminal("localhost", 2222)
        banner = term.connect()
        assert len(banner) > 0

        greeting = term.login()
        assert len(greeting) > 0

        output = term.send_and_wait("")
        assert isinstance(output, str)

        term.disconnect()
