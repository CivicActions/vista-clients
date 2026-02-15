# Data Model: VistA Terminal Library

**Feature**: 002-vista-terminal-library  
**Date**: 2026-02-15  
**Source**: [spec.md](spec.md), [research.md](research.md)

---

## Entities

### 1. TerminalSession

Represents an interactive SSH connection to a VistA environment.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| host | `str` | Yes | IP address or hostname of VistA server |
| port | `int` | Yes | SSH port (default: 2222) |
| timeout | `float` | Yes | Connection timeout in seconds (default: 30.0) |
| prompt_timeout | `float` | Yes | Time to wait for a prompt after sending a command (default: 30.0) |
| settle_delay | `float` | Yes | Quiet period before evaluating prompts (default: 0.5) |
| state | `SessionState` | Derived | Current position in the state machine |
| terminal_type | `str` | Yes | Terminal type to select at VistA prompt (default: "C-VT100") |

**State Machine**:
```
DISCONNECTED → CONNECTED → AUTHENTICATED
     ↑_______________|______________|
            disconnect()
```

| State | Meaning | Allowed Operations |
|-------|---------|--------------------|
| DISCONNECTED | No SSH connection | `connect()` |
| CONNECTED | SSH established, OS login done, VistA loaded, at VistA prompt | `login()`, `send()`, `send_and_wait()`, `wait_for()`, `disconnect()` |
| AUTHENTICATED | VistA Access/Verify codes accepted, at main menu | `send()`, `send_and_wait()`, `wait_for()`, `disconnect()` |

**Invariants**:
- `port` must be 1–65535
- `timeout` must be > 0
- `prompt_timeout` must be > 0
- `settle_delay` must be ≥ 0
- State only advances forward (except disconnect resets to DISCONNECTED)
- `login()` MUST NOT be called in DISCONNECTED state (raises StateError)

---

### 2. PromptPattern

Represents a regular expression used to detect when VistA is
ready for input.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| pattern | `re.Pattern` | Yes | Compiled regex pattern |
| category | `PromptCategory` | Yes | Classification of the prompt |
| name | `str` | Yes | Human-readable label (for logging/debugging) |

**Default Patterns**:

| Name | Category | Pattern |
|------|----------|---------|
| `select_option` | NAVIGATION | `Select .+ Option:` |
| `select_name` | NAVIGATION | `Select .+:\s*$` |
| `device` | NAVIGATION | `DEVICE:` |
| `default_value` | NAVIGATION | `//\s*$` |
| `access_code` | LOGIN | `ACCESS CODE:` |
| `verify_code` | LOGIN | `VERIFY CODE:` |
| `terminal_type` | LOGIN | `Select TERMINAL TYPE NAME:` |
| `press_return` | PAGINATION | `[Pp]ress\s+<?RETURN>?\s+to\s+continue` |

**Pattern Matching Order**: Patterns MUST be evaluated from most-specific to least-specific within each category. In particular, `select_option` (`Select .+ Option:`) and `terminal_type` (`Select TERMINAL TYPE NAME:`) MUST be checked before `select_name` (`Select .+:\s*$`) to avoid false matches. The `login()` method uses only LOGIN-category patterns and known login-flow prompts rather than the full default set.
| `caret_stop` | PAGINATION | `'\^'\s+TO\s+STOP` |
| `end_of_report` | PAGINATION | `END OF REPORT` |
| `type_enter` | PAGINATION | `[Tt]ype\s+<Enter>\s+to\s+continue` |

**Invariants**:
- Pattern must be a valid compiled regex
- Category determines how the library handles the prompt match

---

### 3. OutputBuffer

Represents the accumulated text received from the terminal.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| raw | `str` | Yes | Complete raw output including escape sequences |
| last_command_output | `str` | Derived | Output from the most recent `send_and_wait()` call |
| history | `list[CommandRecord]` | Derived | Ordered list of all command/output pairs |

**Invariants**:
- `raw` is append-only during a session (never truncated)
- `last_command_output` is cleared and replaced on each `send_and_wait()` call
- `history` entries are ordered chronologically

---

### 4. CommandRecord

Represents a single command-and-response exchange.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| command | `str` | Yes | The command string that was sent |
| output | `str` | Yes | The cleaned output between command echo and next prompt |
| raw_output | `str` | Yes | The raw output including escape sequences |
| prompt | `str` | Yes | The prompt text that terminated this exchange |
| timestamp | `float` | Yes | Unix timestamp when the command was sent |

---

### 5. Credentials

Represents authentication details at two levels.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| ssh_user | `str` | Yes | OS-level SSH username (default: "vehutied") |
| ssh_password | `str` | Yes | OS-level SSH password (default: "tied") |
| access_code | `str` | Yes | VistA Access Code (default: "PRO1234") |
| verify_code | `str` | Yes | VistA Verify Code (default: "PRO1234!!") |
| ssh_source | `CredentialSource` | Derived | How SSH credentials were obtained |
| vista_source | `CredentialSource` | Derived | How VistA credentials were obtained |

**Credential Resolution Order** (same for both SSH and VistA):
1. Explicit arguments (if provided)
2. Environment variables
3. Built-in VEHU defaults

---

### 6. AutoScrollConfig

Represents settings for automated pagination handling.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| enabled | `bool` | Yes | Whether auto-scroll is active (default: False) |
| max_pages | `int` | Yes | Maximum pages before stopping (default: 100) |
| patterns | `list[PromptPattern]` | Yes | Pagination prompt patterns to recognise |

**Invariants**:
- `max_pages` must be ≥ 1
- When `enabled` is False, pagination prompts are treated as normal prompts
- When `max_pages` is reached, auto-scroll stops and returns accumulated output

---

## Enumerations

### SessionState
```python
class SessionState(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"        # SSH done, OS login done, VistA loaded
    AUTHENTICATED = "authenticated" # VistA Access/Verify accepted
```

### PromptCategory
```python
class PromptCategory(enum.Enum):
    NAVIGATION = "navigation"   # Standard VistA menu/input prompts
    LOGIN = "login"             # ACCESS CODE, VERIFY CODE, TERMINAL TYPE
    PAGINATION = "pagination"   # Press RETURN to continue, etc.
    CUSTOM = "custom"           # User-defined patterns
```

### CredentialSource
```python
class CredentialSource(enum.Enum):
    EXPLICIT = "explicit"       # Passed directly by caller
    ENVIRONMENT = "environment" # From environment variables
    DEFAULT = "default"         # Built-in VEHU defaults
```

---

## Relationships

```
TerminalSession 1──1 OutputBuffer
TerminalSession 1──1 AutoScrollConfig
TerminalSession 1──* PromptPattern (default + custom)
TerminalSession 1──1 Credentials (for authentication)
OutputBuffer    1──* CommandRecord (over lifetime)
```

**Implementation Note**: The `TerminalSession` entity is implemented as the `VistATerminal` class in `vista_test.terminal.session`.

---

## Internal Transport Entities

### SSHTransport (internal — wraps paramiko)

| Field | Type | Description |
|-------|------|-------------|
| client | `paramiko.SSHClient` | SSH client instance |
| channel | `paramiko.Channel` | Interactive shell channel |
| is_connected | `bool` | Whether the SSH channel is open |

### ExpectChannel (internal — prompt detection engine)

| Field | Type | Description |
|-------|------|-------------|
| channel | `paramiko.Channel` | Underlying SSH channel |
| buffer | `str` | Accumulated unprocessed output |
| timeout | `float` | Default prompt timeout |
| settle_delay | `float` | Quiet period before evaluating matches |
