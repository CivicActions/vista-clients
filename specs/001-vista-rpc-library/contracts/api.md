# API Contracts: VistA RPC Broker Library

**Feature**: 001-vista-rpc-library  
**Date**: 2026-02-14  
**Package**: `vista_test.rpc`

---

## Public API Surface

### Module: `vista_test.rpc`

The public API is re-exported from `vista_test/rpc/__init__.py`. Users import from this single entry point.

---

## 1. `VistABroker` — Primary API Class

**Module**: `vista_test.rpc.broker`

The high-level orchestrator for the full RPC Broker lifecycle.

### Constructor

```python
class VistABroker:
    def __init__(
        self,
        host: str,
        port: int = 9430,
        *,
        timeout: float = 30.0,
        app_name: str = "vista-test",
    ) -> None:
        """Create a VistA RPC Broker client.

        Args:
            host: IP address or hostname of the VistA server.
            port: TCP port of the RPC Broker listener.
            timeout: Connection and read timeout in seconds.
            app_name: Application name sent during TCPConnect handshake.

        Raises:
            ValueError: If port or timeout is out of valid range.
        """
```

### Methods

```python
def connect(self) -> None:
    """Establish TCP connection and perform XWB handshake.

    Executes the full sequence: TCP connect → TCPConnect command →
    server ack. After this call, the session is in HANDSHAKED state.

    Raises:
        ConnectionError: If TCP connection fails or times out.
        HandshakeError: If the server rejects the TCPConnect command.
        StateError: If already connected.
    """

def authenticate(
    self,
    access_code: str | None = None,
    verify_code: str | None = None,
) -> str:
    """Authenticate with VistA using Access/Verify codes.

    Credential resolution order:
    1. Explicit arguments (if both provided)
    2. Environment variables VISTA_ACCESS_CODE / VISTA_VERIFY_CODE
    3. Built-in VEHU defaults (SM1234 / SM1234!!)

    Args:
        access_code: VistA Access Code (optional).
        verify_code: VistA Verify Code (optional).

    Returns:
        The authenticated user's DUZ (str).

    Raises:
        AuthenticationError: If credentials are rejected.
        StateError: If not connected/handshaked.
    """

def create_context(self, option_name: str) -> None:
    """Set the application context for RPC authorization.

    The option_name is automatically encrypted before transmission.

    Args:
        option_name: Name of the B-type option in VistA OPTION (#19) file.

    Raises:
        ContextError: If the context cannot be established.
        StateError: If not authenticated.
    """

def call_rpc(
    self,
    rpc_name: str,
    params: list["RPCParameter"] | None = None,
) -> "RPCResponse":
    """Invoke a remote procedure call on the VistA server.

    Args:
        rpc_name: Name of the RPC to invoke.
        params: Ordered list of typed parameters (default: no parameters).

    Returns:
        RPCResponse containing the parsed server response.

    Raises:
        RPCError: If the server returns an error.
        ConnectionError: If the connection is broken mid-call.
        StateError: If context has not been set.
    """

def ping(self) -> None:
    """Send XWB IM HERE keepalive to reset server timeout.

    Raises:
        ConnectionError: If the connection is broken.
        StateError: If not connected.
    """

def disconnect(self) -> None:
    """Send disconnect command and close the TCP connection.

    Safe to call multiple times. No-op if already disconnected.
    """

@property
def is_connected(self) -> bool:
    """Whether the broker has an active connection."""

@property
def duz(self) -> str | None:
    """DUZ of the authenticated user, or None if not authenticated."""

@property
def state(self) -> "SessionState":
    """Current session state."""
```

### Context Manager Protocol

```python
def __enter__(self) -> "VistABroker":
    """Enter context manager. Calls connect() if not already connected."""

def __exit__(self, exc_type, exc_val, exc_tb) -> None:
    """Exit context manager. Calls disconnect()."""
```

### Usage Example

```python
from vista_test.rpc import VistABroker, literal

with VistABroker("localhost", 9430) as broker:
    broker.authenticate()
    broker.create_context("OR CPRS GUI CHART")
    response = broker.call_rpc("ORWU USERINFO")
    print(response.value)
```

---

## 2. `RPCParameter` — Parameter Construction

**Module**: `vista_test.rpc.protocol`

### Factory Functions (preferred API)

```python
def literal(value: str) -> RPCParameter:
    """Create a literal (string) parameter.

    Args:
        value: The string value to pass.

    Returns:
        RPCParameter with type LITERAL.
    """

def list_param(entries: dict[str, str]) -> RPCParameter:
    """Create a list (key-value array) parameter.

    A list parameter must be the last parameter in the RPC's
    parameter list per the XWB protocol specification.

    Args:
        entries: Dictionary of string keys to string values.

    Returns:
        RPCParameter with type LIST.

    Raises:
        ValueError: If entries is empty.
    """
```

### Class Definition

```python
@dataclass(frozen=True)
class RPCParameter:
    """A typed parameter for an RPC invocation.

    Attributes:
        param_type: LITERAL or LIST.
        value: String value (for LITERAL type).
        entries: Key-value pairs (for LIST type).
    """
    param_type: ParamType
    value: str = ""
    entries: dict[str, str] = field(default_factory=dict)
```

---

## 3. `RPCResponse` — Response Container

**Module**: `vista_test.rpc.protocol`

```python
@dataclass(frozen=True)
class RPCResponse:
    """Parsed response from an RPC call.

    Attributes:
        raw: The raw response string from the server.
        value: Single value (for SINGLE VALUE responses), or None.
        lines: List of values (for ARRAY responses), or None.
    """
    raw: str
    value: str | None = None
    lines: list[str] | None = None

    @property
    def is_array(self) -> bool:
        """Whether this response contains multiple values."""
```

---

## 4. Enumerations

**Module**: `vista_test.rpc.protocol`

```python
class ParamType(enum.Enum):
    """RPC parameter types supported by the XWB protocol."""
    LITERAL = 0
    LIST = 2

class SessionState(enum.Enum):
    """States in the broker session state machine."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"      # Internal/transient — not reachable via public API
    HANDSHAKED = "handshaked"
    AUTHENTICATED = "authenticated"
    CONTEXT_SET = "context_set"
```

---

## 5. Exception Hierarchy

**Module**: `vista_test.rpc.errors`

```python
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
```

---

## 6. Internal Contracts (not public API)

### Transport Layer — `vista_test.rpc.transport`

```python
class Transport:
    """TCP socket wrapper with XWB framing."""

    def __init__(self, host: str, port: int, timeout: float) -> None: ...
    def connect(self) -> None: ...
    def send(self, data: bytes) -> None: ...
    def receive(self) -> str: ...  # Reads until chr(4) terminator
    def close(self) -> None: ...
    @property
    def is_connected(self) -> bool: ...
```

### Protocol Layer — `vista_test.rpc.protocol`

```python
# Message construction
def build_rpc_message(name: str, params: list[RPCParameter] | None = None) -> bytes: ...
def build_connect_message(hostname: str, app_name: str) -> bytes: ...
def build_disconnect_message() -> bytes: ...

# Encoding primitives
def spack(value: str) -> str: ...  # chr(len) + value
def lpack(value: str) -> str: ...  # zero-padded 3-digit len + value

# Cipher operations
def encrypt(plaintext: str) -> str: ...
def decrypt(ciphertext: str) -> str: ...

# Response parsing (handles security/error prefix from XWBRW.m SNDERR)
def parse_response(raw: str) -> RPCResponse:
    """Parse a raw server response into an RPCResponse.

    Extracts the length-prefixed security and application error
    packets from the response head. Raises RPCError if either
    packet is non-empty. Otherwise, parses the remaining data
    as single value or array.

    Args:
        raw: Full response string (after chr(4) stripping).

    Returns:
        RPCResponse with value or lines populated.

    Raises:
        RPCError: If security or application error packet is non-empty.
    """
    ...
```

---

## Re-exports from `vista_test.rpc.__init__`

```python
from vista_test.rpc.broker import VistABroker
from vista_test.rpc.protocol import (
    RPCParameter,
    RPCResponse,
    ParamType,
    SessionState,
    literal,
    list_param,
)
from vista_test.rpc.errors import (
    VistAError,
    ConnectionError,
    HandshakeError,
    AuthenticationError,
    ContextError,
    RPCError,
    StateError,
)
```
