# Feature Specification: VistA Terminal Library

**Feature Branch**: `002-vista-terminal-library`  
**Created**: 2026-02-14  
**Status**: Draft  
**Input**: User description: "Vista Terminal Library - SSH/Telnet interactive session driver for VistA Roll-and-Scroll testing"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Session Lifecycle Management (Priority: P1)

As a test developer, I want to start a VistA interactive session
via SSH, handle the OS-level login, and arrive at the VistA
environment so that I can access menus and workflows not exposed
via RPC. When I am finished, I want to cleanly disconnect the
session.

**Why this priority**: Without a working session, no other
terminal functionality is possible. This is the foundational
prerequisite for every downstream operation—prompt detection,
navigation, and screen scraping all depend on having an
established, authenticated terminal session.

**Independent Test**: Can be fully tested by opening an SSH
connection to the VEHU container on port 2222, authenticating
at the OS level with the known credentials (vista/vista),
verifying that the VistA environment loads and presents an
initial prompt, and then disconnecting cleanly. Delivers value
as proof that the transport layer and OS-level authentication
work end-to-end.

**Acceptance Scenarios**:

1. **Given** a running VEHU container with SSH on port 2222,
   **When** the caller requests a session with default settings,
   **Then** an SSH connection is established, the OS-level login
   is completed automatically, and the VistA environment loads
   within the default timeout.
2. **Given** a running VEHU container, **When** the caller
   provides a custom connection timeout, **Then** that timeout
   is honoured for the SSH connection attempt.
3. **Given** no server is reachable at the specified address,
   **When** the caller requests a session, **Then** a clear
   connection error is raised before the timeout expires.
4. **Given** an established VistA terminal session, **When** the
   caller disconnects, **Then** the SSH channel and transport
   are closed gracefully and the session object reports itself as
   disconnected.
5. **Given** a session used within a context manager (`with`
   block), **When** the block exits (normally or via exception),
   **Then** the session is automatically closed and all
   underlying resources are released.
6. **Given** invalid OS-level credentials, **When** the caller
   attempts to start a session, **Then** a clear authentication
   error is raised indicating the OS login failed.

---

### User Story 2 - Prompt Recognition and Command Execution (Priority: P2)

As a test developer, I want the library to reliably detect when
VistA is ready for input (the "prompt") and allow me to send
commands that wait for the next prompt before returning, so that
I never send commands into the void or read incomplete output.

**Why this priority**: Prompt detection is the fundamental
synchronisation mechanism for any terminal interaction. Without
it, every downstream operation—menu navigation, report capture,
data entry—is unreliable. It depends on a working session
(US 1).

**Independent Test**: Can be tested by starting a VEHU session,
waiting for the initial VistA prompt, sending a known menu
option, and verifying the library correctly detects the next
prompt and returns the intervening output.

**Acceptance Scenarios**:

1. **Given** a VistA session that has just loaded, **When** the
   library waits for a prompt, **Then** it detects the initial
   VistA prompt (e.g., `Select OPTION NAME:`) and returns any
   preceding banner text.
2. **Given** a VistA session at a known prompt, **When** the
   caller sends a command string, **Then** the command is
   transmitted, the library waits for the next prompt, and the
   output between the command echo and the new prompt is
   returned.
3. **Given** a VistA session, **When** the caller provides a
   custom prompt pattern (regex), **Then** the library uses that
   pattern instead of the default set to detect readiness.
4. **Given** a VistA session at a prompt, **When** the caller
   sends a command but the expected prompt does not appear within
   the timeout, **Then** a clear timeout error is raised
   containing the partial output received so far.
5. **Given** a VistA session, **When** the server presents any of
   the standard VistA prompt forms (`Select OPTION NAME:`,
   `USERNAME:`, `DEVICE:`, `//`, `Select ...:`), **Then** the
   default prompt patterns recognise each one.

---

### User Story 3 - Pagination Handling / Auto-Scroll (Priority: P3)

As a test developer, I want the library to automatically advance
through paginated VistA output (handling "Press return to
continue" or similar pagination prompts) so that I can capture
the full text of a long report without writing custom loops for
every test.

**Why this priority**: Many VistA reports and list displays
paginate output, requiring the user to press Enter to continue.
Without auto-scroll, test developers must manually handle
pagination in every test that reads multi-page output. It depends
on prompt recognition (US 2).

**Independent Test**: Can be tested by navigating to a VistA
menu that produces a multi-page listing, enabling auto-scroll,
and verifying that the library captures the complete output
across all pages.

**Acceptance Scenarios**:

1. **Given** a VistA session displaying paginated output with a
   "Press return to continue" or similar pagination prompt,
   **When** auto-scroll is enabled, **Then** the library
   automatically sends a return keystroke at each pagination
   prompt and accumulates all output until the final prompt
   appears.
2. **Given** auto-scroll is disabled (the default), **When** a
   pagination prompt appears, **Then** the library treats it as
   a normal prompt and returns control to the caller with the
   partial output.
3. **Given** auto-scroll is enabled and a paginated report
   exceeds a configurable maximum number of pages, **When** the
   page limit is reached, **Then** the library stops scrolling,
   returns the output collected so far, and indicates truncation.
4. **Given** auto-scroll is enabled, **When** the pagination
   prompt text varies (e.g., `Press RETURN to continue`,
   `'^' TO STOP`), **Then** the library recognises the common
   VistA pagination patterns.

---

### User Story 4 - Screen Buffer Extraction (Priority: P4)

As a test developer, I want to extract text from the session's
accumulated output buffer so that I can verify that specific
content (e.g., a patient's name, a field value) appears in the
terminal output.

**Why this priority**: Screen scraping is the primary mechanism
for asserting correctness in terminal-based tests. It depends on
prompt recognition (US 2) and optionally pagination handling
(US 3) to ensure the buffer contains complete output.

**Independent Test**: Can be tested by sending a command that
produces known output, then extracting the buffer and verifying
that expected strings are present.

**Acceptance Scenarios**:

1. **Given** a VistA session where a command has been executed
   and output has been received, **When** the caller requests the
   output buffer, **Then** the library returns the full text
   output from the most recent command.
2. **Given** a VistA session with accumulated output from
   multiple commands, **When** the caller requests the session
   history, **Then** the library returns the complete output
   history since the session started.
3. **Given** terminal output that contains VT100 escape sequences
   (cursor positioning, colour codes), **When** the caller
   requests cleaned output, **Then** the library strips control
   sequences and returns human-readable plain text.
4. **Given** the caller is looking for a specific string in the
   output, **When** the caller searches the buffer for a pattern,
   **Then** the library supports substring and regex matching
   against the cleaned output.

---

### User Story 5 - VistA Application Login (Priority: P5)

As a test developer, I want the library to handle VistA
application-level authentication (Access Code / Verify Code
entry at the VistA login prompts) after the OS-level SSH login,
so that my session is authorised to access clinical menus and
patient data.

**Why this priority**: Most meaningful VistA workflows require
an authenticated application session beyond the OS-level login.
This bridges the gap between "connected to VistA" and "able to
do clinical work." It depends on session lifecycle (US 1) and
prompt recognition (US 2).

**Independent Test**: Can be tested by starting a VEHU session,
navigating through the VistA login prompts, entering the
demonstration Access Code and Verify Code, and verifying that
the session arrives at the main VistA menu.

**Acceptance Scenarios**:

1. **Given** a VistA session at the application login prompts,
   **When** the caller provides valid Access Code and Verify Code
   credentials, **Then** the library enters them at the
   appropriate prompts and the session arrives at the main VistA
   menu.
2. **Given** no credentials are explicitly provided, **When**
   the caller requests VistA login, **Then** the library uses
   default VEHU demonstration credentials sourced from
   environment variables or built-in defaults.
3. **Given** invalid VistA credentials, **When** the caller
   attempts VistA login, **Then** a clear authentication error
   is raised with the server-provided rejection message.
4. **Given** the VistA login process presents an unrecognised
   intermediate prompt (e.g., an unexpected device selection or
   confirmation prompt), **Then** the library raises a clear
   error containing the unrecognised prompt text, allowing the
   caller to handle it explicitly.

---

### Edge Cases

- What happens when the SSH server is reachable but the VistA
  environment fails to load (e.g., the MUMPS process crashes at
  startup)? The library must detect the absence of an expected
  VistA prompt and raise a session-initialisation error rather
  than hanging indefinitely.
- What happens when the terminal output contains embedded null
  bytes or binary data (e.g., corrupted escape sequences)? The
  library must handle or strip non-printable characters
  gracefully without crashing.
- What happens when a prompt pattern matches mid-output (false
  positive)? The library uses a 500ms settling delay (FR-029)
  before evaluating prompt patterns, ensuring output has
  stopped arriving before declaring a prompt match.
- What happens when the SSH connection drops mid-session (e.g.,
  network interruption)? The library must detect the broken
  channel and raise a connection error rather than blocking on
  reads.
- What happens when VistA output arrives in very small chunks
  (byte-at-a-time) due to network fragmentation? The library
  must accumulate output and only evaluate prompt patterns after
  a brief quiet period.
- What happens when auto-scroll encounters an infinite loop
  (pagination prompt that never resolves to a final prompt)?
  The page-limit safeguard must prevent unbounded scrolling.
- What happens when the caller sends a command while a previous
  command's output is still arriving? The library must enforce
  sequential command execution—only one command in flight at a
  time.

## Clarifications

### Session 2026-02-15

- Q: How should the library handle SSH host key verification? → A: Accept any host key (no verification) — this is a test driver targeting ephemeral Docker containers where host keys change on each launch
- Q: What should the settling delay be for prompt detection? → A: 500 milliseconds — wait for output to stop arriving before evaluating prompt patterns
- Q: Should the library enforce a session state machine, and what states? → A: Three states: DISCONNECTED → CONNECTED → AUTHENTICATED. Commands requiring VistA authentication fail early if attempted on a merely connected session.
- Q: What SSH dependency strategy should the library use? → A: A pure-Python SSH library is the sole allowed external dependency — no system ssh binary required
- Q: How should the library handle unrecognised intermediate prompts during VistA login? → A: Raise an error on any unrecognised intermediate prompt, requiring the caller to handle it
- Q: What are the correct VEHU SSH credentials? → A: SSH user `vehutied` (password `tied`), not `vista`/`vista`. The `vehutied` account auto-launches `mumps -r ZU`. VistA application credentials: `PRO1234`/`PRO1234!!` (PROGRAMMER,ONE)
- Q: What prompts appear during the VistA login sequence? → A: After SSH auth: banner text, then `ACCESS CODE:`, `VERIFY CODE:`, `Select TERMINAL TYPE NAME: C-VT100//`, then main menu `Select ... Option:`

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST establish interactive terminal
  sessions to a VistA server via SSH, connecting to a
  configurable host and port.
- **FR-002**: The library MUST support a configurable connection
  timeout, defaulting to 30 seconds.
- **FR-003**: The library MUST automatically handle OS-level
  authentication (username and password entry) during SSH
  session establishment.
- **FR-004**: The library MUST source default OS-level
  credentials from environment variables (`VISTA_SSH_USER`,
  `VISTA_SSH_PASSWORD`) and fall back to built-in VEHU defaults
  (`vehutied`/`tied`) when no overrides are provided.
- **FR-005**: The library MUST emulate a VT100-compatible
  terminal so that VistA's screen formatting (cursor
  positioning, line drawing) renders correctly or can be
  stripped reliably.
- **FR-006**: The library MUST detect VistA prompts using
  configurable regular expression patterns, with a default set
  covering common VistA prompts: `Select OPTION NAME:`,
  `USERNAME:`, `ACCESS CODE:`, `VERIFY CODE:`, `DEVICE:`, `//`,
  and `Select ...:` variants.
- **FR-007**: The library MUST provide a command-send method that
  transmits input, waits for the next prompt (or timeout), and
  returns the output received between the command echo and the
  new prompt.
- **FR-008**: The library MUST support a configurable prompt
  timeout (time to wait for a prompt after sending a command),
  defaulting to 30 seconds.
- **FR-009**: The library MUST provide an auto-scroll feature
  that automatically advances through paginated VistA output by
  sending return keystrokes at recognised pagination prompts.
- **FR-010**: The auto-scroll feature MUST be disabled by
  default and explicitly enabled by the caller.
- **FR-011**: The auto-scroll feature MUST support a configurable
  maximum page count to prevent unbounded scrolling, defaulting
  to 100 pages.
- **FR-012**: The library MUST recognise common VistA pagination
  patterns including "Press return to continue", "'^' TO STOP",
  and similar variants.
- **FR-013**: The library MUST maintain an output buffer that
  stores the text received from the most recent command
  execution.
- **FR-014**: The library MUST provide access to the complete
  session output history since the session was established.
- **FR-015**: The library MUST provide a method to strip VT100
  and ANSI escape sequences from output, returning clean
  plain-text.
- **FR-016**: The library MUST support searching the output
  buffer by substring and by regular expression.
- **FR-017**: The library MUST support VistA application-level
  authentication by entering Access Code and Verify Code at the
  appropriate VistA login prompts.
- **FR-018**: The library MUST source default VistA credentials
  from environment variables (`VISTA_ACCESS_CODE`,
  `VISTA_VERIFY_CODE`) and fall back to built-in VEHU defaults
  (`PRO1234`/`PRO1234!!`) when no overrides are provided.
- **FR-019**: The library MUST raise distinct, typed errors for:
  connection failures, OS-level authentication failures, VistA
  authentication failures, prompt timeout, and session state
  violations.
- **FR-020**: The library MUST gracefully close sessions,
  releasing the SSH channel and transport.
- **FR-021**: The library MUST support Python's context manager
  protocol (`with` statement) to guarantee that sessions are
  closed when the context exits, whether normally or via an
  exception.
- **FR-022**: The library MUST enforce sequential command
  execution—only one command may be in flight at a time.
  The library MUST also enforce session state ordering:
  VistA login MUST NOT be attempted in DISCONNECTED state,
  and operations requiring authentication MUST NOT be
  attempted in CONNECTED (unauthenticated) state. Violations
  MUST raise a distinct session state error.
- **FR-023**: The library MUST detect broken SSH connections
  (e.g., server crash, network interruption) and raise a
  connection error rather than blocking indefinitely.
- **FR-024**: The library MUST emit log output using Python's
  standard logging module: DEBUG level for raw terminal I/O,
  INFO level for lifecycle events (connect, login, disconnect).
  Credential values MUST be redacted in all log output
  regardless of level.
- **FR-025**: The library MUST NOT implement automatic retry
  logic for connection or command failures. Each operation MUST
  fail immediately on error, allowing callers to implement
  their own retry policies.
- **FR-026**: The library MUST use a pure-Python SSH library
  as its sole external dependency and MUST NOT require a
  system-installed `ssh` binary or any platform-specific
  compiled extensions.
- **FR-027**: The library MUST run identically on macOS, Linux,
  and Windows without conditional platform logic.
- **FR-028**: The library MUST accept any SSH host key without
  verification. Host key checking is disabled because the
  library targets ephemeral test containers whose keys change
  on every launch.
- **FR-029**: The library MUST use a configurable settling delay
  (default 500 milliseconds) before evaluating prompt patterns.
  Output is only considered complete when no new data has
  arrived for the duration of the settling delay.
- **FR-030**: During VistA application login, the library MUST
  raise a distinct error if an unrecognised intermediate prompt
  is encountered. The error MUST include the unrecognised prompt
  text. The library MUST NOT silently accept or auto-respond to
  unexpected login prompts.

### Key Entities

- **Terminal Session**: Represents an interactive connection to
  a VistA environment over SSH. Key attributes: host, port,
  timeouts, connected status, terminal type, session state.
  Valid states: DISCONNECTED (no connection), CONNECTED (SSH
  established and OS login complete, VistA environment loaded),
  AUTHENTICATED (VistA Access/Verify codes accepted). Transitions
  are strictly ordered: DISCONNECTED → CONNECTED → AUTHENTICATED.
  Disconnection from any state returns to DISCONNECTED.
- **Prompt Pattern**: Represents a regular expression used to
  detect when VistA is ready for input. Key attributes: pattern
  string, prompt type (navigation, login, pagination, custom).
- **Output Buffer**: Represents the accumulated text received
  from the terminal. Key attributes: raw content (with escape
  sequences), cleaned content (plain text), command boundaries.
- **Credentials**: Represents authentication details at two
  levels—OS-level (SSH username/password) and VistA
  application-level (Access Code/Verify Code). Key attributes:
  credential values, source (environment variable, explicit, or
  default).
- **Auto-Scroll Configuration**: Represents the settings for
  automated pagination handling. Key attributes: enabled flag,
  maximum page count, pagination prompt patterns.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can connect to a VEHU container,
  arrive at a VistA menu, and send a command in under 15 lines
  of Python code.
- **SC-002**: The library successfully completes the full
  lifecycle (SSH connect → OS login → VistA login → send
  command → read output → disconnect) against the
  `worldvista/vehu` container on SSH port 2222.
- **SC-003**: The library correctly detects all standard VistA
  prompt types (option selection, login, device, continuation)
  with zero false negatives in a standard VEHU session.
- **SC-004**: The auto-scroll feature captures 100% of a
  multi-page VistA report without manual intervention.
- **SC-005**: Connection failures, authentication failures,
  prompt timeouts, and session errors each produce distinct
  error types that a caller can catch individually.
- **SC-006**: Output containing VT100 escape sequences is
  cleaned to readable plain text with no residual control
  characters.
- **SC-007**: 100% of smoke tests pass against a fresh VEHU
  container, covering connection, OS login, VistA login,
  command execution, pagination, and disconnection.
- **SC-008**: The library runs identically inside a minimal
  Linux container with only Python and SSH client dependencies
  installed.

## Assumptions

### Terminology

- **Roll-and-Scroll**: The traditional VistA terminal interface
  where output scrolls vertically and users interact by typing
  at text prompts. Distinct from the ScreenMan form-based
  interface which uses cursor-addressed screen regions.
- **VT100**: A terminal emulation standard that VistA uses for
  screen formatting, cursor positioning, and line drawing.
- **Access Code**: The first half of a VistA credential pair,
  analogous to a username. Entered at the VistA application
  login prompt.
- **Verify Code**: The second half of a VistA credential pair,
  analogous to a password. Entered at the VistA application
  login prompt.
- **VEHU**: VistA for Education, Hacking, and Underground — the
  WorldVistA Docker image used as the reference environment.
- **Pagination Prompt**: A VistA prompt that appears when output
  exceeds one screen, typically "Press return to continue" or
  similar text, requiring user input to display the next page.
- **Prompt**: A text pattern displayed by VistA indicating the
  system is ready to accept user input (e.g., `Select OPTION
  NAME:`, `DEVICE:`).

### Project Assumptions

- The WorldVistA VEHU Docker image exposes SSH on port 2222 by
  default with OS-level credentials `vehutied`/`tied`. The
  `vehutied` account's login shell automatically runs
  `mumps -r ZU` to enter the VistA environment.
- The VEHU image ships with pre-configured demonstration
  credentials (Access Code: `PRO1234`, Verify Code: `PRO1234!!`)
  for the PROGRAMMER,ONE user, which provides Systems Manager
  access for smoke testing VistA application login.
- VistA's terminal interface uses VT100 escape sequences for
  formatting; the library need not support full ScreenMan
  (form-based) interactions in this initial version.
- ScreenMan form navigation (cursor-addressed field entry,
  form-level validation) is out of scope for this specification;
  the library targets Roll-and-Scroll interactions only.
- Telnet support is out of scope for this initial version; SSH
  is the sole transport. Telnet may be added in a future
  iteration if legacy environments require it.
- Performance tuning (connection pooling, multiplexed sessions)
  is out of scope; the library targets correctness and
  single-session usage first.
- The library is a driver/SDK, not a testing tool—it contains
  no test assertions or test-framework dependencies in its
  public API.
- VEHU Docker containers regenerate SSH host keys on each
  launch; strict host key verification is neither practical
  nor security-relevant in this testing context.
