"""VistA terminal interaction library.

Provides ``VistATerminal`` for programmatic access to VistA's
Roll-and-Scroll menu interface via SSH.

Usage::

    from vista_clients.terminal import VistATerminal

    with VistATerminal("localhost", 2222) as term:
        term.login()
        output = term.send_and_wait("Systems Manager Menu")
"""

from vista_clients.terminal.errors import (
    AuthenticationError,
    LoginPromptError,
    PromptTimeoutError,
    SessionError,
    StateError,
    TerminalConnectionError,
    TerminalError,
)
from vista_clients.terminal.session import (
    CommandRecord,
    SessionState,
    VistATerminal,
)
from vista_clients.terminal.vt100 import strip_escape_sequences

__all__ = [
    "AuthenticationError",
    "CommandRecord",
    "LoginPromptError",
    "PromptTimeoutError",
    "SessionError",
    "SessionState",
    "StateError",
    "TerminalConnectionError",
    "TerminalError",
    "VistATerminal",
    "strip_escape_sequences",
]
