"""Smoke tests for VistA terminal lifecycle against VEHU.

These tests require a running VEHU Docker container on port 2222.
"""

from __future__ import annotations

import pytest

from vista_test.terminal.errors import (
    AuthenticationError,
    ConnectionError,
    PromptTimeoutError,
)
from vista_test.terminal.session import SessionState, VistATerminal

pytestmark = pytest.mark.smoke


class TestSessionLifecycle:
    """US1: SSH connect, state verification, and disconnect."""

    def test_connect_and_disconnect(self) -> None:
        """T020: Connect to VEHU, verify CONNECTED state, disconnect."""
        term = VistATerminal("localhost", 2222)
        banner = term.connect()
        try:
            assert term.state == SessionState.CONNECTED
            assert term.is_connected is True
            assert len(banner) > 0
        finally:
            term.disconnect()
        assert term.state == SessionState.DISCONNECTED
        assert term.is_connected is False

    def test_context_manager_auto_close(self) -> None:
        """T021: Context manager auto-disconnects."""
        with VistATerminal("localhost", 2222) as term:
            assert term.state == SessionState.CONNECTED
        assert term.state == SessionState.DISCONNECTED

    def test_unreachable_host_raises_connection_error(self) -> None:
        """T022: Connection to unreachable host raises ConnectionError."""
        term = VistATerminal("192.0.2.1", 2222, timeout=3.0)
        with pytest.raises(ConnectionError):
            term.connect()


class TestCommandExecution:
    """US2: Send commands and receive prompt-synchronised output."""

    def test_send_command_and_read_output(self) -> None:
        """T028: Connect, login, send a command, verify output."""
        with VistATerminal("localhost", 2222) as term:
            term.login()
            assert term.state == SessionState.AUTHENTICATED
            # Send a menu option (just press enter to see current menu)
            output = term.send_and_wait("")
            assert isinstance(output, str)

    def test_send_and_wait_with_custom_prompt(self) -> None:
        """T029: send_and_wait() with custom prompt pattern."""
        with VistATerminal("localhost", 2222) as term:
            term.login()
            # Use a custom pattern that matches the Select Option prompt
            output = term.send_and_wait("", prompt=r"Select .+ Option:")
            assert isinstance(output, str)

    def test_prompt_timeout_raises(self) -> None:
        """T030: Prompt timeout raises PromptTimeoutError with partial_output."""
        with VistATerminal("localhost", 2222, prompt_timeout=2.0, settle_delay=0.1) as term:
            term.login()
            with pytest.raises(PromptTimeoutError) as exc_info:
                term.send_and_wait("", prompt=r"NEVER_MATCH_THIS_PROMPT", timeout=1.0)
            assert isinstance(exc_info.value.partial_output, str)


class TestVistaLogin:
    """US5: VistA application login."""

    def test_login_with_defaults(self) -> None:
        """T035: Login with VEHU defaults, verify AUTHENTICATED."""
        with VistATerminal("localhost", 2222) as term:
            greeting = term.login()
            assert term.state == SessionState.AUTHENTICATED
            # Greeting should contain user info
            assert len(greeting) > 0

    def test_login_with_invalid_credentials(self) -> None:
        """T036: Login with bad credentials raises AuthenticationError."""
        with VistATerminal("localhost", 2222) as term:
            with pytest.raises((AuthenticationError, PromptTimeoutError)):
                term.login(access_code="INVALID", verify_code="INVALID")


class TestAutoScroll:
    """US3: Pagination handling / auto-scroll."""

    def test_auto_scroll_disabled_default(self) -> None:
        """T041: auto_scroll disabled by default."""
        with VistATerminal("localhost", 2222) as term:
            assert term.auto_scroll is False


class TestBufferExtraction:
    """US4: Screen buffer extraction."""

    def test_session_history_tracking(self) -> None:
        """T046: Execute commands and verify session_history."""
        with VistATerminal("localhost", 2222) as term:
            term.login()
            # Send a command
            term.send_and_wait("")
            assert len(term.session_history) >= 1
            record = term.session_history[-1]
            assert hasattr(record, "command")
            assert hasattr(record, "output")
            assert hasattr(record, "timestamp")


class TestFullLifecycle:
    """T050: Full lifecycle smoke test."""

    def test_connect_login_command_disconnect(self) -> None:
        """Full lifecycle: connect → login → command → disconnect."""
        term = VistATerminal("localhost", 2222)
        banner = term.connect()
        assert "VEHU" in banner or len(banner) > 0

        term.login()
        assert term.state == SessionState.AUTHENTICATED

        output = term.send_and_wait("")
        assert isinstance(output, str)
        assert term.last_output == output

        term.disconnect()
        assert term.state == SessionState.DISCONNECTED
