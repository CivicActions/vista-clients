# Data Model: VistA RPC Broker Library

**Feature**: 001-vista-rpc-library  
**Date**: 2026-02-14  
**Source**: [spec.md](spec.md), [research.md](research.md)

---

## Entities

### 1. VistAConnection

Represents a TCP socket session to a VistA RPC Broker.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| host | `str` | Yes | IP address or hostname of VistA server |
| port | `int` | Yes | TCP port of RPC Broker listener (default: 9430) |
| timeout | `float` | Yes | Connection/read timeout in seconds (default: 30.0) |
| is_connected | `bool` | Derived | Whether the TCP socket is currently open |

**Lifecycle**: Created → Connected → Closed  
**Invariants**:
- `port` must be 1–65535
- `timeout` must be > 0
- Socket is non-None only when `is_connected` is True

---

### 2. BrokerSession

Represents the authenticated state of a VistA RPC Broker session. Wraps a `VistAConnection` and tracks the handshake/auth state machine.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| connection | `VistAConnection` | Yes | Underlying TCP connection |
| state | `SessionState` | Derived | Current position in the state machine |
| duz | `str \| None` | Derived | User's DUZ after successful authentication |
| context | `str \| None` | Derived | Currently active application context option name |

**State Machine**:
```
DISCONNECTED → CONNECTED → HANDSHAKED → AUTHENTICATED → CONTEXT_SET
                                                          ↕
                                                    (can switch context)
     ↑_______________________________________________|
                       disconnect()
```

| State | Allowed Operations |
|-------|--------------------|
| DISCONNECTED | `connect()` |
| CONNECTED | *(transient — internal to `connect()`, not reachable via public API)* |
| HANDSHAKED | `authenticate()`, `ping()`, `disconnect()` |
| AUTHENTICATED | `create_context()`, `ping()`, `disconnect()` |
| CONTEXT_SET | `call_rpc()`, `create_context()` (switch), `ping()`, `disconnect()` |

**Invariants**:
- `duz` is non-None only when state ≥ AUTHENTICATED
- `context` is non-None only when state = CONTEXT_SET
- State only advances forward (except disconnect resets to DISCONNECTED)

---

### 3. RPCRequest

Represents a single RPC invocation with typed parameters.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | `str` | Yes | RPC name (e.g., `"XUS SIGNON SETUP"`) |
| parameters | `list[RPCParameter]` | No | Ordered list of parameters (default: empty) |

**Invariants**:
- `name` must be non-empty, max 255 characters (S-PACK limit)
- Parameters are ordered by position (0-indexed)

---

### 4. RPCParameter

Represents a single typed parameter to an RPC.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| param_type | `ParamType` | Yes | Type of parameter (LITERAL or LIST) |
| value | `str` | Conditional | String value (for LITERAL type) |
| entries | `dict[str, str]` | Conditional | Key-value pairs (for LIST type) |

**Validation Rules**:
- When `param_type` is LITERAL: `value` must be set, `entries` is ignored
- When `param_type` is LIST: `entries` must be set, `value` is ignored
- List parameters must be the last parameter in the parameter list

---

### 5. RPCResponse

Represents the parsed result of an RPC call.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| raw | `str` | Yes | Raw response string (after stripping null prefix and EOT) |
| value | `str \| None` | Derived | Single value (for SINGLE VALUE responses) |
| lines | `list[str] \| None` | Derived | Array of values (for ARRAY/GLOBAL ARRAY responses) |

**Parsing Rules**:
- Extract the length-prefixed security packet and application error packet from the response head (per `XWBRW.m` `SNDERR`). If either is non-empty, raise `RPCError` with the message.
- If the remaining result data contains `\r\n`, it is an array response → split on `\r\n` → populate `lines`
- Otherwise, it is a single value response → populate `value`
- Empty response → `value = ""`

---

### 6. Credentials *(internal — resolved within `authenticate()`, not a public API type)*

Represents an Access Code / Verify Code pair with provenance tracking.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| access_code | `str` | Yes | VistA Access Code |
| verify_code | `str` | Yes | VistA Verify Code |
| source | `CredentialSource` | Derived | How the credentials were obtained |

---

## Enumerations

### ParamType
```python
class ParamType(enum.Enum):
    LITERAL = 0   # String value
    LIST = 2      # Key-value array (Mult)
```

### SessionState
```python
class SessionState(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    HANDSHAKED = "handshaked"
    AUTHENTICATED = "authenticated"
    CONTEXT_SET = "context_set"
```

### CredentialSource *(internal — not part of public API re-exports)*
```python
class CredentialSource(enum.Enum):
    EXPLICIT = "explicit"       # Passed directly by caller
    ENVIRONMENT = "environment" # From environment variables
    DEFAULT = "default"         # Built-in built-in demonstration defaults
```

---

## Relationships

```
BrokerSession 1──1 VistAConnection
BrokerSession 1──* RPCRequest (over lifetime)
RPCRequest    1──* RPCParameter
RPCRequest    1──1 RPCResponse (per call)
BrokerSession 1──1 Credentials (for authentication)
```

---

## Wire Format Entities (Internal)

These are internal to the protocol layer but important for implementation:

### XWBMessage
Internal representation of a wire-format message before serialization.

| Field | Type | Description |
|-------|------|-------------|
| command_type | `CommandType` | COMMAND (4) or RPC (2) |
| name | `str` | RPC or command name |
| parameters | `list[RPCParameter]` | Parameters to encode |

### CommandType
```python
class CommandType(enum.Enum):
    COMMAND = 4   # TCPConnect, disconnect
    RPC = 2       # Standard RPC invocation
```
