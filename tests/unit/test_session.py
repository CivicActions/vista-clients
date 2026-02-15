"""Unit tests for VistATerminal session lifecycle.

Tests constructor validation, state machine transitions, SSH credential
resolution, context manager, send_and_wait, login, auto-scroll,
and buffer properties using mock transport/expect.
"""

from __future__ import annotations

import os
import re
from unittest.mock import MagicMock, patch

import pytest

from vista_test.terminal.errors import StateError
from vista_test.terminal.session import (
    CredentialSource,
    SessionState,
    VistATerminal,
    _resolve_ssh_credentials,
    _resolve_vista_credentials,
)

# ---------------------------------------------------------------------------
# Constructor validation (T014)
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    """VistATerminal constructor rejects invalid parameters."""

    def test_default_values(self) -> None:
        term = VistATerminal()
        assert term.state == SessionState.DISCONNECTED
        assert term.is_connected is False

    def test_port_too_low(self) -> None:
        with pytest.raises(ValueError, match="port must be"):
            VistATerminal(port=0)

    def test_port_too_high(self) -> None:
        with pytest.raises(ValueError, match="port must be"):
            VistATerminal(port=65536)

    def test_port_boundary_low(self) -> None:
        term = VistATerminal(port=1)
        assert term._port == 1

    def test_port_boundary_high(self) -> None:
        term = VistATerminal(port=65535)
        assert term._port == 65535

    def test_timeout_zero(self) -> None:
        with pytest.raises(ValueError, match="timeout must be"):
            VistATerminal(timeout=0)

    def test_timeout_negative(self) -> None:
        with pytest.raises(ValueError, match="timeout must be"):
            VistATerminal(timeout=-1.0)

    def test_prompt_timeout_zero(self) -> None:
        with pytest.raises(ValueError, match="prompt_timeout must be"):
            VistATerminal(prompt_timeout=0)

    def test_settle_delay_negative(self) -> None:
        with pytest.raises(ValueError, match="settle_delay must be"):
            VistATerminal(settle_delay=-0.1)

    def test_settle_delay_zero_allowed(self) -> None:
        term = VistATerminal(settle_delay=0)
        assert term._settle_delay == 0


# ---------------------------------------------------------------------------
# SSH credential resolution (T015)
# ---------------------------------------------------------------------------


class TestSSHCredentialResolution:
    """SSH credential resolution follows explicit → env → defaults."""

    def test_explicit_credentials(self) -> None:
        user, pw, source = _resolve_ssh_credentials("myuser", "mypass")
        assert user == "myuser"
        assert pw == "mypass"
        assert source == CredentialSource.EXPLICIT

    def test_environment_credentials(self) -> None:
        with patch.dict(
            os.environ,
            {"VISTA_SSH_USER": "envuser", "VISTA_SSH_PASSWORD": "envpass"},
        ):
            user, pw, source = _resolve_ssh_credentials(None, None)
            assert user == "envuser"
            assert pw == "envpass"
            assert source == CredentialSource.ENVIRONMENT

    def test_default_credentials(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            user, pw, source = _resolve_ssh_credentials(None, None)
            assert user == "vehutied"
            assert pw == "tied"
            assert source == CredentialSource.DEFAULT

    def test_explicit_overrides_env(self) -> None:
        with patch.dict(
            os.environ,
            {"VISTA_SSH_USER": "envuser", "VISTA_SSH_PASSWORD": "envpass"},
        ):
            user, pw, source = _resolve_ssh_credentials("explicit", "explicit")
            assert user == "explicit"
            assert source == CredentialSource.EXPLICIT

    def test_partial_env_falls_through_to_default(self) -> None:
        """If only one env var is set, fall through to defaults."""
        with patch.dict(os.environ, {"VISTA_SSH_USER": "envuser"}, clear=True):
            user, pw, source = _resolve_ssh_credentials(None, None)
            assert user == "vehutied"
            assert source == CredentialSource.DEFAULT


class TestVistaCredentialResolution:
    """VistA credential resolution follows explicit → env → defaults."""

    def test_explicit_credentials(self) -> None:
        ac, vc, source = _resolve_vista_credentials("ACC", "VER")
        assert ac == "ACC"
        assert vc == "VER"
        assert source == CredentialSource.EXPLICIT

    def test_environment_credentials(self) -> None:
        with patch.dict(
            os.environ,
            {"VISTA_ACCESS_CODE": "EACC", "VISTA_VERIFY_CODE": "EVER"},
        ):
            ac, vc, source = _resolve_vista_credentials(None, None)
            assert ac == "EACC"
            assert vc == "EVER"
            assert source == CredentialSource.ENVIRONMENT

    def test_default_credentials(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            ac, vc, source = _resolve_vista_credentials(None, None)
            assert ac == "PRO1234"
            assert vc == "PRO1234!!"
            assert source == CredentialSource.DEFAULT


# ---------------------------------------------------------------------------
# State machine transitions (T018)
# ---------------------------------------------------------------------------


class TestStateTransitions:
    """State machine enforces valid transitions."""

    def test_initial_state_is_disconnected(self) -> None:
        term = VistATerminal()
        assert term.state == SessionState.DISCONNECTED

    def test_connect_requires_disconnected(self) -> None:
        term = VistATerminal()
        term._state = SessionState.CONNECTED
        with pytest.raises(StateError, match="connect"):
            term.connect()

    def test_connect_when_authenticated_raises(self) -> None:
        term = VistATerminal()
        term._state = SessionState.AUTHENTICATED
        with pytest.raises(StateError, match="connect"):
            term.connect()

    def test_disconnect_from_disconnected_is_noop(self) -> None:
        term = VistATerminal()
        term.disconnect()  # Should not raise
        assert term.state == SessionState.DISCONNECTED

    def test_disconnect_resets_to_disconnected(self) -> None:
        term = VistATerminal()
        term._state = SessionState.CONNECTED
        mock_transport = MagicMock()
        term._transport = mock_transport
        term._expect = MagicMock()
        term.disconnect()
        assert term.state == SessionState.DISCONNECTED
        mock_transport.close.assert_called_once()

    def test_is_connected_false_when_disconnected(self) -> None:
        term = VistATerminal()
        assert term.is_connected is False

    def test_is_connected_true_when_connected(self) -> None:
        term = VistATerminal()
        term._state = SessionState.CONNECTED
        assert term.is_connected is True

    def test_is_connected_true_when_authenticated(self) -> None:
        term = VistATerminal()
        term._state = SessionState.AUTHENTICATED
        assert term.is_connected is True


# ---------------------------------------------------------------------------
# Context manager (T017)
# ---------------------------------------------------------------------------


class TestContextManager:
    """Context manager calls connect/disconnect automatically."""

    @patch.object(VistATerminal, "connect", return_value="banner")
    @patch.object(VistATerminal, "disconnect")
    def test_context_manager_connects_and_disconnects(
        self, mock_disconnect: MagicMock, mock_connect: MagicMock
    ) -> None:
        with VistATerminal() as term:
            mock_connect.assert_called_once()
            assert term is not None
        mock_disconnect.assert_called_once()

    @patch.object(VistATerminal, "connect", return_value="banner")
    @patch.object(VistATerminal, "disconnect")
    def test_context_manager_disconnects_on_exception(
        self, mock_disconnect: MagicMock, mock_connect: MagicMock
    ) -> None:
        with pytest.raises(RuntimeError):
            with VistATerminal():
                raise RuntimeError("test error")
        mock_disconnect.assert_called_once()

    @patch.object(VistATerminal, "disconnect")
    def test_context_manager_skips_connect_if_already_connected(
        self, mock_disconnect: MagicMock
    ) -> None:
        term = VistATerminal()
        term._state = SessionState.CONNECTED
        with term:
            pass  # Should not call connect()
        mock_disconnect.assert_called_once()


# ---------------------------------------------------------------------------
# State enforcement helpers (T018)
# ---------------------------------------------------------------------------


class TestStateEnforcement:
    """State enforcement helpers raise StateError correctly."""

    def test_require_state_passes(self) -> None:
        term = VistATerminal()
        term._require_state(SessionState.DISCONNECTED, "connect")  # No raise

    def test_require_state_fails(self) -> None:
        term = VistATerminal()
        with pytest.raises(StateError) as exc_info:
            term._require_state(SessionState.CONNECTED, "login")
        assert exc_info.value.current_state == "disconnected"
        assert exc_info.value.required_state == "connected"

    def test_require_connected_passes_when_connected(self) -> None:
        term = VistATerminal()
        term._state = SessionState.CONNECTED
        term._require_connected("send")  # No raise

    def test_require_connected_passes_when_authenticated(self) -> None:
        term = VistATerminal()
        term._state = SessionState.AUTHENTICATED
        term._require_connected("send")  # No raise

    def test_require_connected_fails_when_disconnected(self) -> None:
        term = VistATerminal()
        with pytest.raises(StateError) as exc_info:
            term._require_connected("send_and_wait")
        assert exc_info.value.current_state == "disconnected"


# ---------------------------------------------------------------------------
# Helper: set up a VistATerminal with mock expect channel
# ---------------------------------------------------------------------------


def _make_connected_terminal() -> tuple[VistATerminal, MagicMock]:
    """Create a VistATerminal in CONNECTED state with a mock expect channel."""
    term = VistATerminal()
    term._state = SessionState.CONNECTED
    mock_expect = MagicMock()
    term._expect = mock_expect
    term._transport = MagicMock()
    return term, mock_expect


# ---------------------------------------------------------------------------
# send_and_wait (T024, T027)
# ---------------------------------------------------------------------------


class TestSendAndWait:
    """Tests for send_and_wait() output cleaning and recording."""

    def test_send_and_wait_returns_cleaned_output(self) -> None:
        term, expect = _make_connected_terminal()
        # Mock expect to return the prompt match
        match = re.search(r"Select .+ Option:", "Select Systems Manager Menu Option: ")
        expect.expect.return_value = (0, match, "command echo\nOutput line 1\nOutput line 2")
        expect.sendline = MagicMock()

        output = term.send_and_wait("test command")
        assert "Output line 1" in output
        expect.sendline.assert_called_once_with("test command")

    def test_send_and_wait_strips_command_echo(self) -> None:
        term, expect = _make_connected_terminal()
        match = re.search(r"Select .+ Option:", "Select Systems Manager Menu Option: ")
        expect.expect.return_value = (0, match, "test command\nActual output")

        output = term.send_and_wait("test command")
        assert output == "Actual output"

    def test_send_and_wait_records_history(self) -> None:
        term, expect = _make_connected_terminal()
        match = re.search(r"Select .+ Option:", "Select Systems Manager Menu Option: ")
        expect.expect.return_value = (0, match, "cmd\nResult")

        term.send_and_wait("cmd")
        assert len(term.session_history) == 1
        record = term.session_history[0]
        assert record.command == "cmd"
        assert record.prompt == "Select Systems Manager Menu Option:"

    def test_send_and_wait_with_custom_prompt(self) -> None:
        term, expect = _make_connected_terminal()
        match = re.search(r"CUSTOM>", "CUSTOM>")
        expect.expect.return_value = (0, match, "output")

        term.send_and_wait("cmd", prompt="CUSTOM>")
        # Should have used custom pattern
        call_args = expect.expect.call_args
        patterns = call_args[0][0]
        assert len(patterns) == 1  # Only custom pattern

    def test_send_and_wait_requires_connected(self) -> None:
        term = VistATerminal()
        with pytest.raises(StateError):
            term.send_and_wait("test")

    def test_send_requires_connected(self) -> None:
        term = VistATerminal()
        with pytest.raises(StateError):
            term.send("test")


# ---------------------------------------------------------------------------
# Auto-scroll (T037, T039)
# ---------------------------------------------------------------------------


class TestAutoScroll:
    """Tests for auto-scroll configuration and pagination handling."""

    def test_auto_scroll_default_false(self) -> None:
        term = VistATerminal()
        assert term.auto_scroll is False

    def test_auto_scroll_setter(self) -> None:
        term = VistATerminal()
        term.auto_scroll = True
        assert term.auto_scroll is True

    def test_max_pages_default(self) -> None:
        term = VistATerminal()
        assert term.max_pages == 100

    def test_max_pages_setter(self) -> None:
        term = VistATerminal()
        term.max_pages = 50
        assert term.max_pages == 50

    def test_max_pages_minimum(self) -> None:
        term = VistATerminal()
        with pytest.raises(ValueError, match="max_pages must be"):
            term.max_pages = 0

    def test_auto_scroll_advances_pagination(self) -> None:
        """When auto_scroll=True, pagination prompts are automatically advanced."""
        term, expect = _make_connected_terminal()
        term._auto_scroll = True

        # First call returns pagination prompt, second returns navigation prompt
        pagination_match = re.search(
            r"[Pp]ress\s+<?RETURN>?\s+to\s+continue",
            "Press <RETURN> to continue",
        )
        nav_match = re.search(r"Select .+ Option:", "Select Systems Manager Menu Option: ")
        expect.expect.side_effect = [
            (0, pagination_match, "Page 1 output"),
            (0, nav_match, "Page 2 output"),
        ]

        term.send_and_wait("report")
        assert expect.sendline.call_count == 2  # command + pagination advance


# ---------------------------------------------------------------------------
# Pagination pattern matching (T039)
# ---------------------------------------------------------------------------


class TestPaginationPatternMatching:
    """Test that pagination patterns are correctly identified."""

    def test_press_return_is_pagination(self) -> None:
        assert VistATerminal._is_pagination_prompt("Press <RETURN> to continue")

    def test_caret_stop_is_pagination(self) -> None:
        assert VistATerminal._is_pagination_prompt("'^' TO STOP")

    def test_end_of_report_is_pagination(self) -> None:
        assert VistATerminal._is_pagination_prompt("END OF REPORT")

    def test_type_enter_is_pagination(self) -> None:
        assert VistATerminal._is_pagination_prompt("Type <Enter> to continue")

    def test_navigation_not_pagination(self) -> None:
        assert not VistATerminal._is_pagination_prompt("Select Systems Manager Menu Option:")


# ---------------------------------------------------------------------------
# Buffer properties (T042, T043, T044, T045)
# ---------------------------------------------------------------------------


class TestBufferProperties:
    """Tests for output buffer properties."""

    def test_last_output_empty_initially(self) -> None:
        term = VistATerminal()
        assert term.last_output == ""

    def test_raw_last_output_empty_initially(self) -> None:
        term = VistATerminal()
        assert term.raw_last_output == ""

    def test_session_history_empty_initially(self) -> None:
        term = VistATerminal()
        assert term.session_history == []

    def test_full_output_empty_initially(self) -> None:
        term = VistATerminal()
        assert term.full_output == ""

    def test_session_history_returns_copy(self) -> None:
        term = VistATerminal()
        h1 = term.session_history
        h2 = term.session_history
        assert h1 is not h2

    def test_contains_finds_substring(self) -> None:
        term = VistATerminal()
        term._last_output = "Hello World from VistA"
        assert term.contains("World")

    def test_contains_misses_absent_substring(self) -> None:
        term = VistATerminal()
        term._last_output = "Hello World"
        assert not term.contains("missing")

    def test_search_finds_pattern(self) -> None:
        term = VistATerminal()
        term._last_output = "Patient: SMITH,JOHN DFN=12345"
        m = term.search(r"DFN=(\d+)")
        assert m is not None
        assert m.group(1) == "12345"

    def test_search_returns_none_on_miss(self) -> None:
        term = VistATerminal()
        term._last_output = "Hello World"
        assert term.search(r"DFN=\d+") is None

    def test_search_accepts_compiled_pattern(self) -> None:
        term = VistATerminal()
        term._last_output = "Result: OK"
        m = term.search(re.compile(r"Result:\s+(\w+)"))
        assert m is not None
        assert m.group(1) == "OK"


# ---------------------------------------------------------------------------
# VistA credential resolution (T034)
# ---------------------------------------------------------------------------


class TestVistaCredentialResolutionExtended:
    """Extended tests for VistA credential resolution order."""

    def test_explicit_overrides_env(self) -> None:
        with patch.dict(
            os.environ,
            {"VISTA_ACCESS_CODE": "EACC", "VISTA_VERIFY_CODE": "EVER"},
        ):
            ac, vc, source = _resolve_vista_credentials("XACC", "XVER")
            assert ac == "XACC"
            assert source == CredentialSource.EXPLICIT

    def test_partial_env_falls_through_to_default(self) -> None:
        with patch.dict(os.environ, {"VISTA_ACCESS_CODE": "EACC"}, clear=True):
            ac, vc, source = _resolve_vista_credentials(None, None)
            assert ac == "PRO1234"
            assert source == CredentialSource.DEFAULT
