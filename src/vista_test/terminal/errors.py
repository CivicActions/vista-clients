"""Exception hierarchy for VistA terminal errors.

All exceptions inherit from ``TerminalError`` so callers can catch
the base class for broad handling or individual subclasses for
specific error conditions.
"""

from __future__ import annotations


class TerminalError(Exception):
    """Base exception for all VistA terminal errors."""


class ConnectionError(TerminalError):
    """SSH connection failure or broken connection.

    Raised when the SSH connection cannot be established, times out,
    or is detected as broken during an operation.
    """


class AuthenticationError(TerminalError):
    """OS-level SSH or VistA application authentication failed.

    Attributes:
        level: Whether the failure was at the ``"ssh"`` or ``"vista"`` level.
    """

    def __init__(self, message: str, *, level: str) -> None:
        super().__init__(message)
        self.level = level


class SessionError(TerminalError):
    """VistA environment failed to load after SSH login.

    Raised when the SSH connection succeeds but the expected VistA
    prompt (e.g. ``ACCESS CODE:``) never appears.
    """


class PromptTimeoutError(TerminalError):
    """Expected prompt did not appear within the timeout.

    Attributes:
        partial_output: The output received before the timeout expired.
        patterns: The prompt patterns that were being matched against.
    """

    def __init__(
        self,
        message: str,
        *,
        partial_output: str,
        patterns: list[str],
    ) -> None:
        super().__init__(message)
        self.partial_output = partial_output
        self.patterns = patterns


class LoginPromptError(TerminalError):
    """Unrecognised prompt encountered during VistA login flow.

    Attributes:
        prompt_text: The unrecognised prompt text that was received.
    """

    def __init__(self, message: str, *, prompt_text: str) -> None:
        super().__init__(message)
        self.prompt_text = prompt_text


class StateError(TerminalError):
    """Operation attempted in an invalid session state.

    Attributes:
        current_state: The current session state.
        required_state: The state required for the operation.
    """

    def __init__(
        self,
        message: str,
        *,
        current_state: str,
        required_state: str,
    ) -> None:
        super().__init__(message)
        self.current_state = current_state
        self.required_state = required_state
