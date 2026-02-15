"""Unit tests for the terminal exception hierarchy."""

from __future__ import annotations

import pytest

from vista_test.terminal.errors import (
    AuthenticationError,
    ConnectionError,
    LoginPromptError,
    PromptTimeoutError,
    SessionError,
    StateError,
    TerminalError,
)


class TestExceptionHierarchy:
    """All terminal errors inherit from TerminalError."""

    def test_connection_error_is_terminal_error(self) -> None:
        err = ConnectionError("cannot connect")
        assert isinstance(err, TerminalError)

    def test_authentication_error_is_terminal_error(self) -> None:
        err = AuthenticationError("bad password", level="ssh")
        assert isinstance(err, TerminalError)

    def test_session_error_is_terminal_error(self) -> None:
        err = SessionError("VistA did not load")
        assert isinstance(err, TerminalError)

    def test_prompt_timeout_error_is_terminal_error(self) -> None:
        err = PromptTimeoutError(
            "timeout",
            partial_output="partial",
            patterns=["pattern1"],
        )
        assert isinstance(err, TerminalError)

    def test_login_prompt_error_is_terminal_error(self) -> None:
        err = LoginPromptError("unexpected", prompt_text="UNKNOWN:")
        assert isinstance(err, TerminalError)

    def test_state_error_is_terminal_error(self) -> None:
        err = StateError(
            "wrong state",
            current_state="disconnected",
            required_state="connected",
        )
        assert isinstance(err, TerminalError)


class TestExceptionAttributes:
    """Each exception carries its specific attributes."""

    def test_authentication_error_level_ssh(self) -> None:
        err = AuthenticationError("bad password", level="ssh")
        assert err.level == "ssh"
        assert str(err) == "bad password"

    def test_authentication_error_level_vista(self) -> None:
        err = AuthenticationError("bad creds", level="vista")
        assert err.level == "vista"

    def test_prompt_timeout_error_partial_output(self) -> None:
        err = PromptTimeoutError(
            "timed out",
            partial_output="some output...",
            patterns=["Select .+ Option:", "DEVICE:"],
        )
        assert err.partial_output == "some output..."
        assert err.patterns == ["Select .+ Option:", "DEVICE:"]

    def test_login_prompt_error_prompt_text(self) -> None:
        err = LoginPromptError(
            "unrecognised prompt",
            prompt_text="Enter something unexpected:",
        )
        assert err.prompt_text == "Enter something unexpected:"

    def test_state_error_states(self) -> None:
        err = StateError(
            "need connected",
            current_state="disconnected",
            required_state="connected",
        )
        assert err.current_state == "disconnected"
        assert err.required_state == "connected"


class TestIndependentCatchability:
    """Each exception type can be caught independently."""

    def test_catch_connection_error(self) -> None:
        with pytest.raises(ConnectionError):
            raise ConnectionError("fail")

    def test_catch_authentication_error(self) -> None:
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("fail", level="ssh")

    def test_catch_session_error(self) -> None:
        with pytest.raises(SessionError):
            raise SessionError("fail")

    def test_catch_prompt_timeout_error(self) -> None:
        with pytest.raises(PromptTimeoutError):
            raise PromptTimeoutError("fail", partial_output="", patterns=[])

    def test_catch_login_prompt_error(self) -> None:
        with pytest.raises(LoginPromptError):
            raise LoginPromptError("fail", prompt_text="X:")

    def test_catch_state_error(self) -> None:
        with pytest.raises(StateError):
            raise StateError("fail", current_state="a", required_state="b")

    def test_catch_base_catches_all(self) -> None:
        """Catching TerminalError catches any subclass."""
        with pytest.raises(TerminalError):
            raise ConnectionError("fail")
        with pytest.raises(TerminalError):
            raise AuthenticationError("fail", level="ssh")
        with pytest.raises(TerminalError):
            raise PromptTimeoutError("fail", partial_output="", patterns=[])

    def test_connection_error_does_not_catch_authentication(self) -> None:
        """ConnectionError catch does NOT match AuthenticationError."""
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("fail", level="ssh")
        # This should NOT be caught as ConnectionError
        try:
            raise AuthenticationError("fail", level="ssh")
        except ConnectionError:
            pytest.fail("AuthenticationError should not be caught as ConnectionError")
        except AuthenticationError:
            pass
