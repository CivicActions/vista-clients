"""VistA terminal session management.

Contains the ``VistATerminal`` high-level orchestrator, session state
machine, types (enums, dataclasses), and default VistA prompt patterns.
"""

from __future__ import annotations

import enum
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple

from vista_test.terminal.errors import (
    AuthenticationError,
    LoginPromptError,
    SessionError,
    StateError,
)
from vista_test.terminal.expect import ExpectChannel
from vista_test.terminal.transport import SSHTransport
from vista_test.terminal.vt100 import strip_escape_sequences

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SessionState(enum.Enum):
    """States in the terminal session state machine."""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"  # SSH done, OS login done, VistA loaded
    AUTHENTICATED = "authenticated"  # VistA Access/Verify accepted


class PromptCategory(enum.Enum):
    """Classification of a VistA prompt pattern."""

    NAVIGATION = "navigation"  # Standard VistA menu / input prompts
    LOGIN = "login"  # ACCESS CODE, VERIFY CODE, TERMINAL TYPE
    PAGINATION = "pagination"  # Press RETURN to continue, etc.
    CUSTOM = "custom"  # User-defined patterns


class CredentialSource(enum.Enum):
    """How a credential value was resolved."""

    EXPLICIT = "explicit"  # Passed directly by caller
    ENVIRONMENT = "environment"  # From environment variables
    DEFAULT = "default"  # Built-in VEHU defaults


# ---------------------------------------------------------------------------
# Data classes / named tuples
# ---------------------------------------------------------------------------


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


class PromptPattern(NamedTuple):
    """A compiled regex paired with its category and a human label."""

    pattern: re.Pattern[str]
    category: PromptCategory
    name: str


# ---------------------------------------------------------------------------
# Default prompt patterns — ordered most-specific first within each category
# ---------------------------------------------------------------------------

# Navigation prompts
_P_SELECT_OPTION = PromptPattern(
    re.compile(r"Select .+ Option:"),
    PromptCategory.NAVIGATION,
    "select_option",
)
_P_SELECT_NAME = PromptPattern(
    re.compile(r"Select .+:\s*$", re.MULTILINE),
    PromptCategory.NAVIGATION,
    "select_name",
)
_P_DEVICE = PromptPattern(
    re.compile(r"DEVICE:"),
    PromptCategory.NAVIGATION,
    "device",
)
_P_DEFAULT_VALUE = PromptPattern(
    re.compile(r"//\s*$", re.MULTILINE),
    PromptCategory.NAVIGATION,
    "default_value",
)

# Login prompts
_P_ACCESS_CODE = PromptPattern(
    re.compile(r"ACCESS CODE:"),
    PromptCategory.LOGIN,
    "access_code",
)
_P_VERIFY_CODE = PromptPattern(
    re.compile(r"VERIFY CODE:"),
    PromptCategory.LOGIN,
    "verify_code",
)
_P_TERMINAL_TYPE = PromptPattern(
    re.compile(r"Select TERMINAL TYPE NAME:"),
    PromptCategory.LOGIN,
    "terminal_type",
)

# Pagination prompts
_P_PRESS_RETURN = PromptPattern(
    re.compile(r"[Pp]ress\s+<?RETURN>?\s+to\s+continue", re.IGNORECASE),
    PromptCategory.PAGINATION,
    "press_return",
)
_P_CARET_STOP = PromptPattern(
    re.compile(r"'\^'\s+TO\s+STOP", re.IGNORECASE),
    PromptCategory.PAGINATION,
    "caret_stop",
)
_P_END_OF_REPORT = PromptPattern(
    re.compile(r"END OF REPORT", re.IGNORECASE),
    PromptCategory.PAGINATION,
    "end_of_report",
)
_P_TYPE_ENTER = PromptPattern(
    re.compile(r"[Tt]ype\s+<Enter>\s+to\s+continue", re.IGNORECASE),
    PromptCategory.PAGINATION,
    "type_enter",
)

# Master list — order matters: more-specific patterns first
DEFAULT_PROMPT_PATTERNS: list[PromptPattern] = [
    # Login (most specific)
    _P_ACCESS_CODE,
    _P_VERIFY_CODE,
    _P_TERMINAL_TYPE,
    # Navigation (specific before general)
    _P_SELECT_OPTION,
    _P_DEVICE,
    _P_DEFAULT_VALUE,
    _P_SELECT_NAME,  # general — must be last among navigation
    # Pagination
    _P_PRESS_RETURN,
    _P_CARET_STOP,
    _P_END_OF_REPORT,
    _P_TYPE_ENTER,
]

NAVIGATION_PATTERNS: list[PromptPattern] = [
    p for p in DEFAULT_PROMPT_PATTERNS if p.category == PromptCategory.NAVIGATION
]
LOGIN_PATTERNS: list[PromptPattern] = [
    p for p in DEFAULT_PROMPT_PATTERNS if p.category == PromptCategory.LOGIN
]
PAGINATION_PATTERNS: list[PromptPattern] = [
    p for p in DEFAULT_PROMPT_PATTERNS if p.category == PromptCategory.PAGINATION
]


# ---------------------------------------------------------------------------
# Credential resolution helpers
# ---------------------------------------------------------------------------

_VEHU_SSH_USER = "vehutied"
_VEHU_SSH_PASSWORD = "tied"
_VEHU_ACCESS_CODE = "PRO1234"
_VEHU_VERIFY_CODE = "PRO1234!!"


def _resolve_ssh_credentials(
    ssh_user: str | None,
    ssh_password: str | None,
) -> tuple[str, str, CredentialSource]:
    """Resolve SSH credentials: explicit → env vars → VEHU defaults."""
    if ssh_user is not None and ssh_password is not None:
        return ssh_user, ssh_password, CredentialSource.EXPLICIT
    env_user = os.environ.get("VISTA_SSH_USER")
    env_pass = os.environ.get("VISTA_SSH_PASSWORD")
    if env_user is not None and env_pass is not None:
        return env_user, env_pass, CredentialSource.ENVIRONMENT
    return _VEHU_SSH_USER, _VEHU_SSH_PASSWORD, CredentialSource.DEFAULT


def _resolve_vista_credentials(
    access_code: str | None,
    verify_code: str | None,
) -> tuple[str, str, CredentialSource]:
    """Resolve VistA credentials: explicit → env vars → VEHU defaults."""
    if access_code is not None and verify_code is not None:
        return access_code, verify_code, CredentialSource.EXPLICIT
    env_ac = os.environ.get("VISTA_ACCESS_CODE")
    env_vc = os.environ.get("VISTA_VERIFY_CODE")
    if env_ac is not None and env_vc is not None:
        return env_ac, env_vc, CredentialSource.ENVIRONMENT
    return _VEHU_ACCESS_CODE, _VEHU_VERIFY_CODE, CredentialSource.DEFAULT


# ---------------------------------------------------------------------------
# VistATerminal — high-level session orchestrator
# ---------------------------------------------------------------------------


class VistATerminal:
    """High-level orchestrator for interactive VistA terminal sessions.

    Manages the full lifecycle: SSH connection, VistA login, command
    execution, pagination handling, and output capture.

    Three-state machine: DISCONNECTED → CONNECTED → AUTHENTICATED.

    Args:
        host: IP address or hostname of the VistA server.
        port: SSH port number.
        timeout: SSH connection timeout in seconds.
        prompt_timeout: Default time to wait for a prompt
            after sending a command.
        settle_delay: Quiet period (seconds) before evaluating
            prompt patterns.
        terminal_type: Terminal type to select at the VistA
            TERMINAL TYPE NAME prompt.

    Raises:
        ValueError: If port, timeout, prompt_timeout, or
            settle_delay is out of valid range.
    """

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
        if not 1 <= port <= 65535:
            raise ValueError(f"port must be 1-65535, got {port}")
        if timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {timeout}")
        if prompt_timeout <= 0:
            raise ValueError(f"prompt_timeout must be > 0, got {prompt_timeout}")
        if settle_delay < 0:
            raise ValueError(f"settle_delay must be >= 0, got {settle_delay}")

        self._host = host
        self._port = port
        self._timeout = timeout
        self._prompt_timeout = prompt_timeout
        self._settle_delay = settle_delay
        self._terminal_type = terminal_type

        self._state = SessionState.DISCONNECTED
        self._transport: SSHTransport | None = None
        self._expect: ExpectChannel | None = None

        # Auto-scroll configuration
        self._auto_scroll = False
        self._max_pages = 100

        # Output buffer tracking
        self._last_output = ""
        self._raw_last_output = ""
        self._full_output = ""
        self._session_history: list[CommandRecord] = []

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(
        self,
        ssh_user: str | None = None,
        ssh_password: str | None = None,
    ) -> str:
        """Establish SSH connection, complete OS login, and arrive at VistA.

        SSH credential resolution order:
        1. Explicit arguments (if both provided)
        2. Environment variables VISTA_SSH_USER / VISTA_SSH_PASSWORD
        3. Built-in VEHU defaults (vehutied / tied)

        Args:
            ssh_user: SSH username (optional).
            ssh_password: SSH password (optional).

        Returns:
            The banner text displayed during connection.

        Raises:
            ConnectionError: If SSH connection fails or times out.
            AuthenticationError: If OS-level password is rejected.
            SessionError: If VistA environment fails to load.
            StateError: If already connected.
        """
        self._require_state(SessionState.DISCONNECTED, "connect")

        username, password, source = _resolve_ssh_credentials(ssh_user, ssh_password)
        logger.info(
            "Connecting to %s:%d (SSH credential source: %s)",
            self._host,
            self._port,
            source.value,
        )

        transport = SSHTransport(self._host, self._port, self._timeout)
        try:
            transport.connect(username, password)
        except Exception:
            transport.close()
            raise

        expect = ExpectChannel(
            transport.channel,
            timeout=self._prompt_timeout,
            settle_delay=self._settle_delay,
        )

        # Wait for the ACCESS CODE prompt (signals VistA is loaded)
        login_regexes = [p.pattern for p in LOGIN_PATTERNS]
        try:
            idx, match, text_before = expect.expect(login_regexes)
        except Exception as exc:
            transport.close()
            raise SessionError(
                "VistA environment failed to load — ACCESS CODE prompt not detected"
            ) from exc

        # Verify we got the ACCESS CODE prompt specifically
        if LOGIN_PATTERNS[idx].name != "access_code":
            transport.close()
            raise SessionError(f"Expected ACCESS CODE prompt but got: {match.group()}")

        self._transport = transport
        self._expect = expect
        self._state = SessionState.CONNECTED
        self._full_output += text_before + match.group()

        banner = strip_escape_sequences(text_before).strip()
        logger.info("Connected — VistA ACCESS CODE prompt detected")
        return banner

    def disconnect(self) -> None:
        """Close the SSH channel and transport.

        Safe to call multiple times. No-op if already disconnected.
        """
        if self._transport is not None:
            logger.info("Disconnecting from %s:%d", self._host, self._port)
            self._transport.close()
            self._transport = None
        self._expect = None
        self._state = SessionState.DISCONNECTED

    def __enter__(self) -> VistATerminal:
        """Enter context manager. Calls connect() if not already connected."""
        if self._state == SessionState.DISCONNECTED:
            self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit context manager. Calls disconnect()."""
        self.disconnect()

    # ------------------------------------------------------------------
    # State properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> SessionState:
        """Current session state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Whether the terminal has an active SSH connection."""
        return self._state in (SessionState.CONNECTED, SessionState.AUTHENTICATED)

    # ------------------------------------------------------------------
    # State enforcement
    # ------------------------------------------------------------------

    def _require_state(self, required: SessionState, operation: str) -> None:
        """Raise StateError if not in the required state."""
        if self._state != required:
            raise StateError(
                f"Cannot {operation}() in {self._state.value} state",
                current_state=self._state.value,
                required_state=required.value,
            )

    def _require_connected(self, operation: str) -> None:
        """Raise StateError if not connected or authenticated."""
        if self._state not in (SessionState.CONNECTED, SessionState.AUTHENTICATED):
            raise StateError(
                f"Cannot {operation}() in {self._state.value} state",
                current_state=self._state.value,
                required_state="connected or authenticated",
            )

    # ------------------------------------------------------------------
    # Command execution (US2 — Phase 4)
    # ------------------------------------------------------------------

    def send(self, text: str) -> None:
        """Send raw text to the terminal without waiting for a prompt.

        Args:
            text: The text to send.

        Raises:
            ConnectionError: If the SSH channel is broken.
            StateError: If not connected.
        """
        self._require_connected("send")
        assert self._expect is not None  # guaranteed by _require_connected
        self._expect.send(text)

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

        Transmits the command followed by a carriage return, then
        blocks until a prompt pattern matches or the timeout expires.

        Args:
            command: The command string to send.
            prompt: Custom prompt pattern for this command only.
            timeout: Override prompt_timeout for this call only.
            auto_scroll: Override session auto_scroll for this call.
            max_pages: Override max_pages for this call only.

        Returns:
            The cleaned output between the command echo and the
            prompt, with VT100 escape sequences stripped.

        Raises:
            PromptTimeoutError: If no prompt matches within timeout.
            ConnectionError: If the SSH channel breaks mid-command.
            StateError: If not connected.
        """
        self._require_connected("send_and_wait")
        assert self._expect is not None

        effective_timeout = timeout if timeout is not None else self._prompt_timeout
        use_auto_scroll = auto_scroll if auto_scroll is not None else self._auto_scroll
        effective_max_pages = max_pages if max_pages is not None else self._max_pages

        # Build pattern list
        patterns = self._build_patterns(prompt)

        # Send command
        cmd_timestamp = time.time()
        self._expect.sendline(command)
        logger.debug("Sent command: %r", command)

        # Collect output, handling pagination if auto_scroll enabled
        raw_parts: list[str] = []
        page_count = 0

        while True:
            _idx, match, text_before = self._expect.expect(patterns, timeout=effective_timeout)
            raw_parts.append(text_before)
            self._full_output += text_before + match.group()

            matched_prompt = match.group()

            # Check if it's a pagination prompt and auto_scroll is on
            if use_auto_scroll and self._is_pagination_prompt(matched_prompt):
                page_count += 1
                if page_count >= effective_max_pages:
                    logger.info("Max pages (%d) reached, stopping auto-scroll", effective_max_pages)
                    break
                # Advance pagination
                self._expect.sendline()
                continue

            # Non-pagination prompt — we're done
            break

        raw_output = "".join(raw_parts)

        # Clean the output: strip command echo, VT100, leading/trailing whitespace
        cleaned = self._clean_output(raw_output, command)

        # Record
        self._last_output = cleaned
        self._raw_last_output = raw_output
        record = CommandRecord(
            command=command,
            output=cleaned,
            raw_output=raw_output,
            prompt=matched_prompt,
            timestamp=cmd_timestamp,
        )
        self._session_history.append(record)

        return cleaned

    def wait_for(
        self,
        pattern: str | re.Pattern[str],
        *,
        timeout: float | None = None,
    ) -> tuple[re.Match[str], str]:
        """Wait for a specific pattern in the output.

        Blocks until the pattern matches the accumulated output
        or the timeout expires. Does not send any input.

        Args:
            pattern: Regex pattern to wait for.
            timeout: Override prompt_timeout for this call.

        Returns:
            Tuple of (match object, text before match).

        Raises:
            PromptTimeoutError: If pattern doesn't match within timeout.
            ConnectionError: If the SSH channel is broken.
            StateError: If not connected.
        """
        self._require_connected("wait_for")
        assert self._expect is not None

        effective_timeout = timeout if timeout is not None else self._prompt_timeout
        compiled = self._compile_pattern(pattern)

        _idx, match, text_before = self._expect.expect([compiled], timeout=effective_timeout)
        self._full_output += text_before + match.group()
        return match, text_before

    # ------------------------------------------------------------------
    # VistA login (US5 — Phase 5)
    # ------------------------------------------------------------------

    def login(
        self,
        access_code: str | None = None,
        verify_code: str | None = None,
    ) -> str:
        """Authenticate with VistA using Access/Verify codes.

        VistA credential resolution order:
        1. Explicit arguments (if both provided)
        2. Environment variables VISTA_ACCESS_CODE / VISTA_VERIFY_CODE
        3. Built-in VEHU defaults (PRO1234 / PRO1234!!)

        Args:
            access_code: VistA Access Code (optional).
            verify_code: VistA Verify Code (optional).

        Returns:
            The greeting text displayed after successful login.

        Raises:
            AuthenticationError: If credentials are rejected.
            LoginPromptError: If an unrecognised intermediate prompt
                is encountered.
            StateError: If not connected, or already authenticated.
        """
        self._require_state(SessionState.CONNECTED, "login")
        assert self._expect is not None

        ac, vc, source = _resolve_vista_credentials(access_code, verify_code)
        logger.info("Logging in to VistA (credential source: %s)", source.value)

        # Send Access Code (we're already at the ACCESS CODE prompt)
        self._expect.sendline(ac)

        # Wait for VERIFY CODE prompt
        login_and_nav = [p.pattern for p in LOGIN_PATTERNS + NAVIGATION_PATTERNS]
        _idx, match, text_before = self._expect.expect(login_and_nav)
        self._full_output += text_before + match.group()

        matched_name = self._identify_prompt(match.group())
        if matched_name != "verify_code":
            if "not a valid" in text_before.lower() or "invalid" in text_before.lower():
                raise AuthenticationError(
                    "VistA Access Code rejected",
                    level="vista",
                )
            raise LoginPromptError(
                f"Expected VERIFY CODE prompt but got: {match.group()}",
                prompt_text=match.group(),
            )

        # Send Verify Code
        self._expect.sendline(vc)

        # Wait for TERMINAL TYPE, a navigation prompt, or rejection
        _idx, match, text_before = self._expect.expect(login_and_nav)
        self._full_output += text_before + match.group()
        matched_name = self._identify_prompt(match.group())

        # Check for auth rejection in the output text
        rejection_markers = [
            "not a valid",
            "verify code must",
            "invalid verify",
        ]
        for marker in rejection_markers:
            if marker in text_before.lower():
                raise AuthenticationError(
                    "VistA credentials rejected",
                    level="vista",
                )

        greeting_parts: list[str] = [text_before]

        # Handle terminal type selection if prompted
        if matched_name == "terminal_type":
            # Accept default terminal type by sending the configured type
            self._expect.sendline(self._terminal_type)
            # Wait for navigation prompt (main menu)
            _idx, match, text_before = self._expect.expect(login_and_nav)
            self._full_output += text_before + match.group()
            greeting_parts.append(text_before)

        # If we got a navigation prompt, we're at the main menu
        self._state = SessionState.AUTHENTICATED
        greeting = strip_escape_sequences("\n".join(greeting_parts)).strip()
        logger.info("Authenticated successfully")
        return greeting

    # ------------------------------------------------------------------
    # Auto-scroll configuration (US3 — Phase 6)
    # ------------------------------------------------------------------

    @property
    def auto_scroll(self) -> bool:
        """Whether auto-scroll is currently enabled (default: False)."""
        return self._auto_scroll

    @auto_scroll.setter
    def auto_scroll(self, value: bool) -> None:
        """Enable or disable auto-scroll for pagination handling."""
        self._auto_scroll = value

    @property
    def max_pages(self) -> int:
        """Maximum pages auto-scroll will advance (default: 100)."""
        return self._max_pages

    @max_pages.setter
    def max_pages(self, value: int) -> None:
        """Set the maximum page count for auto-scroll."""
        if value < 1:
            raise ValueError(f"max_pages must be >= 1, got {value}")
        self._max_pages = value

    # ------------------------------------------------------------------
    # Output buffer properties (US4 — Phase 7)
    # ------------------------------------------------------------------

    @property
    def last_output(self) -> str:
        """The cleaned output from the most recent send_and_wait() call."""
        return self._last_output

    @property
    def raw_last_output(self) -> str:
        """The raw output from the most recent send_and_wait() call."""
        return self._raw_last_output

    @property
    def session_history(self) -> list[CommandRecord]:
        """Complete ordered list of all command/output exchanges."""
        return list(self._session_history)

    @property
    def full_output(self) -> str:
        """Complete raw output received since session start."""
        return self._full_output

    def contains(self, text: str) -> bool:
        """Check if text appears in the last command output (cleaned).

        Args:
            text: Substring to search for.

        Returns:
            True if found, False otherwise.
        """
        return text in self._last_output

    def search(self, pattern: str | re.Pattern[str]) -> re.Match[str] | None:
        """Search the last command output (cleaned) for a regex pattern.

        Args:
            pattern: Regex pattern to search for.

        Returns:
            Match object if found, None otherwise.
        """
        compiled = self._compile_pattern(pattern)
        return compiled.search(self._last_output)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_patterns(
        self,
        custom_prompt: str | re.Pattern[str] | None,
    ) -> list[re.Pattern[str]]:
        """Build the list of compiled patterns for expect().

        If a custom prompt is provided, it's used as the sole pattern.
        Otherwise, the default prompt patterns (excluding LOGIN) are used.
        """
        if custom_prompt is not None:
            return [self._compile_pattern(custom_prompt)]
        # Use navigation + pagination patterns (not login prompts)
        return [p.pattern for p in NAVIGATION_PATTERNS + PAGINATION_PATTERNS]

    @staticmethod
    def _compile_pattern(pattern: str | re.Pattern[str]) -> re.Pattern[str]:
        """Compile a string pattern to a regex, or pass through compiled."""
        if isinstance(pattern, str):
            return re.compile(pattern)
        return pattern

    @staticmethod
    def _is_pagination_prompt(prompt_text: str) -> bool:
        """Check if the matched prompt text is a pagination prompt."""
        return any(pp.pattern.search(prompt_text) for pp in PAGINATION_PATTERNS)

    @staticmethod
    def _identify_prompt(prompt_text: str) -> str | None:
        """Identify a prompt by matching against all known patterns."""
        for pp in DEFAULT_PROMPT_PATTERNS:
            if pp.pattern.search(prompt_text):
                return pp.name
        return None

    def _clean_output(self, raw_output: str, command: str) -> str:
        """Clean raw output: strip command echo, VT100 sequences."""
        cleaned = strip_escape_sequences(raw_output)
        # Remove command echo (first line often echoes the command)
        lines = cleaned.split("\n")
        if lines and command and lines[0].strip() == command.strip():
            lines = lines[1:]
        cleaned = "\n".join(lines).strip()
        return cleaned
