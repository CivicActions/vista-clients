"""Exception hierarchy for the VistA RPC Broker library.

All exceptions inherit from ``VistAError`` so callers can catch the
base class for broad error handling or individual subclasses for
fine-grained control.
"""


class VistAError(Exception):
    """Base exception for all VistA RPC Broker errors."""


class ConnectionError(VistAError):
    """TCP connection failure or broken connection."""


class HandshakeError(VistAError):
    """XWB protocol handshake was rejected by the server."""


class AuthenticationError(VistAError):
    """Access/Verify code authentication failed."""


class ContextError(VistAError):
    """Application context could not be established."""


class RPCError(VistAError):
    """Remote procedure call returned an error."""


class StateError(VistAError):
    """Operation attempted in an invalid session state."""
