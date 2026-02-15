"""VistA terminal interaction library.

Provides ``VistATerminal`` for programmatic access to VistA's
Roll-and-Scroll menu interface via SSH.

Usage::

    from vista_test.terminal import VistATerminal

    with VistATerminal("localhost", 2222) as term:
        term.login()
        output = term.send_and_wait("Systems Manager Menu")
"""

from vista_test.terminal.errors import (
    AuthenticationError,
    ConnectionError,
    LoginPromptError,
    PromptTimeoutError,
    SessionError,
    StateError,
    TerminalError,
)
from vista_test.terminal.session import (
    CommandRecord,
    SessionState,
    VistATerminal,
)
from vista_test.terminal.vt100 import strip_escape_sequences

__all__ = [
    "AuthenticationError",
    "CommandRecord",
    "ConnectionError",
    "LoginPromptError",
    "PromptTimeoutError",
    "SessionError",
    "SessionState",
    "StateError",
    "TerminalError",
    "VistATerminal",
    "strip_escape_sequences",
]
