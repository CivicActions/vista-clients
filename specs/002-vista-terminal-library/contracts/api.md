# API Contracts: VistA Terminal Library

**Feature**: 002-vista-terminal-library  
**Date**: 2026-02-15  
**Package**: `vista_clients.terminal`

---

## Public API Surface

### Module: `vista_clients.terminal`

The public API is re-exported from `vista_clients/terminal/__init__.py`. Users import from this single entry point.

---

## 1. `VistATerminal` — Primary API Class

**Module**: `vista_clients.terminal.session`

The high-level orchestrator for interactive VistA terminal sessions.

### Constructor

```python
class VistATerminal:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 2222,
        *,
        timeout: float = 30.0,
        prompt_timeout: float = 30.0,
        settle_delay: float = 0.5,
        terminal_type: str = "C-VT100",
    ) -> None:
        """Create a VistA terminal session driver.

        Args:
            host: IP address or hostname of the VistA server.
            port: SSH port number.
            timeout: SSH connection timeout in seconds.
            prompt_timeout: Default time to wait for a prompt
                after sending a command.
            settle_delay: Quiet period (seconds) before evaluating
                prompt patterns. Output is only considered complete
                when no new data has arrived for this duration.
            terminal_type: Terminal type to select at the VistA
                TERMINAL TYPE NAME prompt.

        Raises:
            ValueError: If port, timeout, prompt_timeout, or
                settle_delay is out of valid range.
        """
```

### Connection & Authentication Methods

```python
def connect(
    self,
    ssh_user: str | None = None,
    ssh_password: str | None = None,
) -> str:
    """Establish SSH connection, complete OS login, and arrive at VistA.

    Performs the full sequence: SSH connect → OS password auth →
    consume banner → arrive at VistA ACCESS CODE prompt. After
    this call, the session is in CONNECTED state.

    SSH credential resolution order:
    1. Explicit arguments (if both provided)
    2. Environment variables VISTA_SSH_USER / VISTA_SSH_PASSWORD
    3. Built-in built-in demonstration defaults (vehutied / tied)

    Args:
        ssh_user: SSH username (optional).
        ssh_password: SSH password (optional).

    Returns:
        The banner text displayed during connection.

    Raises:
        ConnectionError: If SSH connection fails or times out.
        AuthenticationError: If OS-level password is rejected.
        SessionError: If VistA environment fails to load
            (no ACCESS CODE prompt appears).
        StateError: If already connected.
    """

def login(
    self,
    access_code: str | None = None,
    verify_code: str | None = None,
) -> str:
    """Authenticate with VistA using Access/Verify codes.

    Enters credentials at the ACCESS CODE and VERIFY CODE prompts,
    accepts the default terminal type, and arrives at the main
    VistA menu. After this call, the session is in AUTHENTICATED
    state.

    VistA credential resolution order:
    1. Explicit arguments (if both provided)
    2. Environment variables VISTA_ACCESS_CODE / VISTA_VERIFY_CODE
    3. Built-in built-in demonstration defaults (PRO1234 / PRO1234!!)

    Args:
        access_code: VistA Access Code (optional).
        verify_code: VistA Verify Code (optional).

    Returns:
        The greeting text displayed after successful login
        (e.g., "Good evening DOCTOR").

    Raises:
        AuthenticationError: If credentials are rejected.
        LoginPromptError: If an unrecognised intermediate prompt
            is encountered during the login flow. The error
            includes the unrecognised prompt text.
        StateError: If not connected, or already authenticated.
    """

def disconnect(self) -> None:
    """Close the SSH channel and transport.

    Safe to call multiple times. No-op if already disconnected.
    Transitions state to DISCONNECTED.
    """
```

### Command Execution Methods

```python
def send(self, text: str) -> None:
    """Send raw text to the terminal without waiting for a prompt.

    Use this for sending keystrokes that don't produce a prompt
    response (e.g., Ctrl-C, individual characters).

    Args:
        text: The text to send.

    Raises:
        ConnectionError: If the SSH channel is broken.
        StateError: If not connected.
    """

def send_and_wait(
    self,
    command: str,
    *,
    prompt: str | re.Pattern[str] | None = None,
    timeout: float | None = None,
    auto_scroll: bool | None = None,
    max_pages: int | None = None,
) -> str:
    """Send a command and wait for the next prompt.

    Transmits the command followed by a newline, then blocks
    until a prompt pattern is matched (after the settling delay)
    or the timeout expires.

    Args:
        command: The command string to send.
        prompt: Custom prompt pattern for this command only.
            If None, uses the session's default prompt patterns.
            Can be a string (compiled as regex) or compiled regex.
        timeout: Override prompt_timeout for this call only.
        auto_scroll: Override session auto_scroll for this call.
            If True, pagination prompts are automatically advanced.
        max_pages: Override max_pages for this call only.

    Returns:
        The cleaned output between the command echo and the
        prompt, with VT100 escape sequences stripped.

    Raises:
        PromptTimeoutError: If no prompt matches within the
            timeout. The error includes partial output received.
        ConnectionError: If the SSH channel breaks mid-command.
        StateError: If not connected.
    """

def wait_for(
    self,
    pattern: str | re.Pattern[str],
    *,
    timeout: float | None = None,
) -> tuple[re.Match[str], str]:
    """Wait for a specific pattern in the output.

    Blocks until the pattern matches the accumulated output
    (after settling delay) or the timeout expires. Does not
    send any input.

    Args:
        pattern: Regex pattern to wait for.
        timeout: Override prompt_timeout for this call.

    Returns:
        Tuple of (match object, text before match).

    Raises:
        PromptTimeoutError: If pattern doesn't match within
            the timeout.
        ConnectionError: If the SSH channel is broken.
        StateError: If not connected.
    """
```

### Output Buffer Methods

```python
@property
def last_output(self) -> str:
    """The cleaned output from the most recent send_and_wait() call.

    Returns empty string if no commands have been executed.
    """

@property
def raw_last_output(self) -> str:
    """The raw output (with escape sequences) from the most
    recent send_and_wait() call."""

@property
def session_history(self) -> list["CommandRecord"]:
    """Complete ordered list of all command/output exchanges
    since the session started."""

@property
def full_output(self) -> str:
    """Complete raw output received since session start."""

def contains(self, text: str) -> bool:
    """Check if text appears in the last command output (cleaned).

    Args:
        text: Substring to search for.

    Returns:
        True if found, False otherwise.
    """

def search(self, pattern: str | re.Pattern[str]) -> re.Match[str] | None:
    """Search the last command output (cleaned) for a regex pattern.

    Args:
        pattern: Regex pattern to search for.

    Returns:
        Match object if found, None otherwise.
    """
```

### Session State Properties

```python
@property
def is_connected(self) -> bool:
    """Whether the terminal has an active SSH connection."""

@property
def state(self) -> "SessionState":
    """Current session state (DISCONNECTED, CONNECTED, or AUTHENTICATED)."""
```

### Auto-Scroll Configuration

```python
@property
def auto_scroll(self) -> bool:
    """Whether auto-scroll is currently enabled (default: False)."""

@auto_scroll.setter
def auto_scroll(self, value: bool) -> None:
    """Enable or disable auto-scroll for pagination handling."""

@property
def max_pages(self) -> int:
    """Maximum pages auto-scroll will advance (default: 100)."""

@max_pages.setter
def max_pages(self, value: int) -> None:
    """Set the maximum page count for auto-scroll."""
```

### Context Manager Protocol

```python
def __enter__(self) -> "VistATerminal":
    """Enter context manager. Calls connect() if not already connected."""

def __exit__(self, exc_type, exc_val, exc_tb) -> None:
    """Exit context manager. Calls disconnect()."""
```

---

## 2. `CommandRecord` — Command/Output Exchange

**Module**: `vista_clients.terminal.session`

```python
@dataclass(frozen=True)
class CommandRecord:
    """Record of a single command-and-response exchange.

    Attributes:
        command: The command string that was sent.
        output: Cleaned output (VT100 stripped) between command
            echo and next prompt.
        raw_output: Raw output including escape sequences.
        prompt: The prompt text that terminated this exchange.
        timestamp: Unix timestamp when the command was sent.
    """
    command: str
    output: str
    raw_output: str
    prompt: str
    timestamp: float
```

---

## 3. Enumerations

**Module**: `vista_clients.terminal.session`

```python
class SessionState(enum.Enum):
    """States in the terminal session state machine."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
```

---

## 4. Utility Functions

**Module**: `vista_clients.terminal.vt100`

```python
def strip_escape_sequences(text: str) -> str:
    """Remove VT100/ANSI escape sequences from text.

    Strips cursor positioning, color codes, device attribute
    responses, and other control sequences, returning clean
    human-readable plain text.

    Args:
        text: Raw terminal output containing escape sequences.

    Returns:
        Cleaned text with all escape sequences removed.
    """
```

---

## 5. Exception Hierarchy

**Module**: `vista_clients.terminal.errors`

```python
class TerminalError(Exception):
    """Base exception for all VistA terminal errors."""

class ConnectionError(TerminalError):
    """SSH connection failure or broken connection."""

class AuthenticationError(TerminalError):
    """OS-level SSH or VistA application authentication failed.

    Attributes:
        level: Whether the failure was at the 'ssh' or 'vista' level.
    """
    level: str  # "ssh" or "vista"

class SessionError(TerminalError):
    """VistA environment failed to load after SSH login."""

class PromptTimeoutError(TerminalError):
    """Expected prompt did not appear within the timeout.

    Attributes:
        partial_output: The output received before the timeout.
        patterns: The prompt patterns that were being matched.
    """
    partial_output: str
    patterns: list[str]

class LoginPromptError(TerminalError):
    """Unrecognised prompt encountered during VistA login flow.

    Attributes:
        prompt_text: The unrecognised prompt text.
    """
    prompt_text: str

class StateError(TerminalError):
    """Operation attempted in an invalid session state.

    Attributes:
        current_state: The current session state.
        required_state: The state required for the operation.
    """
    current_state: str
    required_state: str
```

---

## 6. Internal Contracts (not public API)

### SSH Transport — `vista_clients.terminal.transport`

```python
class SSHTransport:
    """Paramiko SSH wrapper for interactive terminal sessions."""

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float,
    ) -> None: ...

    def connect(
        self,
        username: str,
        password: str,
        terminal_type: str = "vt100",
    ) -> None:
        """Establish SSH connection, authenticate, and open
        interactive shell with pty."""

    @property
    def channel(self) -> "paramiko.Channel":
        """The interactive shell channel."""

    def close(self) -> None: ...

    @property
    def is_connected(self) -> bool: ...
```

### Expect Engine — `vista_clients.terminal.expect`

```python
class ExpectChannel:
    """pexpect-style interface over a paramiko Channel."""

    def __init__(
        self,
        channel: "paramiko.Channel",
        timeout: float = 30.0,
        settle_delay: float = 0.5,
    ) -> None: ...

    def expect(
        self,
        patterns: list[re.Pattern[str]],
        timeout: float | None = None,
    ) -> tuple[int, re.Match[str], str]:
        """Block until one of the patterns matches after settle period.

        Returns:
            Tuple of (matched pattern index, match object,
            text before the match).

        Raises:
            PromptTimeoutError: If no pattern matches within timeout.
        """

    def send(self, text: str) -> None:
        """Send text to the channel."""

    def sendline(self, text: str = "") -> None:
        """Send text followed by carriage return."""

    @property
    def buffer(self) -> str:
        """Current unprocessed output in the buffer."""
```

---

## Re-exports from `vista_clients.terminal.__init__`

```python
from vista_clients.terminal.session import (
    VistATerminal,
    CommandRecord,
    SessionState,
)
from vista_clients.terminal.vt100 import strip_escape_sequences
from vista_clients.terminal.errors import (
    TerminalError,
    ConnectionError,
    AuthenticationError,
    SessionError,
    PromptTimeoutError,
    LoginPromptError,
    StateError,
)
```
