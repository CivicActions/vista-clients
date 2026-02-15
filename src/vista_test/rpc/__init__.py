"""VistA RPC Broker library.

Public API re-exports for ``vista_test.rpc``.
"""

from vista_test.rpc.broker import VistABroker
from vista_test.rpc.errors import (
    AuthenticationError,
    ConnectionError,
    ContextError,
    HandshakeError,
    RPCError,
    StateError,
    VistAError,
)
from vista_test.rpc.protocol import (
    CipherType,
    ParamType,
    RPCParameter,
    RPCResponse,
    SessionState,
    list_param,
    literal,
)

__all__ = [
    "AuthenticationError",
    "CipherType",
    "ConnectionError",
    "ContextError",
    "HandshakeError",
    "ParamType",
    "RPCError",
    "RPCParameter",
    "RPCResponse",
    "SessionState",
    "StateError",
    "VistABroker",
    "VistAError",
    "list_param",
    "literal",
]
