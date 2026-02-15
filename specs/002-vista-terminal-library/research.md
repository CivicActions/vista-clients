# Research: VistA Terminal Library

**Feature**: 002-vista-terminal-library  
**Date**: 2026-02-15  
**Sources**: VEHU Docker container SSH session capture, ZU.m MUMPS source (via MCP), GMTSUP.m pagination source (via MCP), XWB*1.1*50 patch notes, paramiko/pexpect documentation, RPC library 001 research

---

## 1. VEHU SSH Login Sequence (Empirically Observed)

### Decision
The login sequence is a five-phase flow: SSH auth → banner
display → VistA ACCESS/VERIFY CODE entry → terminal type
selection → main menu arrival.

### Observed Sequence

Connection: `ssh -p 2222 vehutied@localhost` (password: `tied`)

```
Phase 1 — SSH connection + OS password
  Prompt: "vehutied@localhost's password:"
  Response: "tied"

Phase 2 — Banner text (no user input required)
  "VEHU or CPRS DEMO INSTANCE - Patched to December 2025"
  [credential table with NAME/ACCESS/VERIFY/E SIG columns]
  [CPRS/Vitals version info]
  "Volume set: ROU:vehu  UCI: VAH  Device: /dev/pts/0"

Phase 3 — VistA Application Login
  Prompt: "ACCESS CODE:"
  Response: e.g., "PRO1234" (echoed as asterisks *******)
  Prompt: "VERIFY CODE:"
  Response: e.g., "PRO1234!!" (echoed as asterisks *********)

  On success: "Good evening DOCTOR"
  On failure: "Not a valid ACCESS CODE/VERIFY CODE pair."
              Then re-prompts "ACCESS CODE:" (up to 3 attempts)

Phase 4 — Terminal Type selection
  Prompt: "Select TERMINAL TYPE NAME: C-VT100//"
  Response: "" (accept default C-VT100)
  Output: "Digital Equipment Corporation VT-100 video"

Phase 5 — Main Menu
  Prompt: "Select Systems Manager Menu <TEST ACCOUNT> Option:"
  (Menu content depends on user's assigned primary menu)
```

### Key Observations

1. **SSH username is `vehutied`, NOT `vista`**. Password is
   `tied`. This is the "tied" user that auto-launches `mumps
   -r ZU` via login shell. The `vista` user drops to a bash
   shell instead.
2. **VistA is launched automatically** by the `vehutied` SSH
   login — no need to manually run `mumps -r ZU`.
3. **Banner text is substantial** — includes a full credentials
   table. The library must consume this output before the
   ACCESS CODE prompt arrives.
4. **Terminal type prompt has a default** (`C-VT100//`) — the
   `//` suffix is the standard VistA "accept default" indicator.
   Sending Enter accepts it.
5. **Access/Verify codes are echoed as asterisks**, not
   suppressed entirely. The library receives `*` characters
   back as echo.
6. **VT100 escape sequences observed**: `\x1b[?1;2c` (device
   attributes response) appeared after the terminal type
   selection. The library must handle or strip these.

### Rationale
Direct SSH connection is simpler and more portable than
`docker exec`. SSH login automatically launches ZU, eliminating
the need to construct a MUMPS invocation. Using `vehutied`
(not `vista`) is essential because the tied account's login
shell invokes `mumps -r ZU` directly.

### Alternatives Considered
- **`docker exec`**: Only works with Docker runtime, not
  portable to remote VistA instances, requires Docker socket
  access in CI. Rejected for library transport.
- **`vista` SSH user + manual `mumps -r ZU`**: Lands at a bash
  shell, requiring an extra command to enter VistA. The `vehutied`
  user eliminates this step. However, the library should support
  configurable usernames for non-VEHU environments.

---

## 2. VistA Prompt Patterns

### Decision
Use a tiered set of default regex patterns covering navigation
prompts, login prompts, pagination prompts, and the default-
value indicator (`//`).

### Observed Prompt Patterns (from VEHU session capture)

| Prompt Text | Category | Regex Pattern |
|-------------|----------|---------------|
| `ACCESS CODE:` | Login | `ACCESS CODE:` |
| `VERIFY CODE:` | Login | `VERIFY CODE:` |
| `Select TERMINAL TYPE NAME: C-VT100//` | Navigation (with default) | `Select .+:.*//` |
| `Select Systems Manager Menu <TEST ACCOUNT> Option:` | Navigation | `Select .+ Option:` |
| `Select .+:` | Navigation (general) | `Select .+:\s*$` |
| `DEVICE:` | Device prompt | `DEVICE:` |
| `// ` (bare default indicator) | Default value | `//\s*$` |
| `Press RETURN to continue` | Pagination | `Press RETURN to continue` |
| `'^' TO STOP` | Pagination | `'\^' TO STOP` |

### Prompt Detection Strategy

The library must distinguish between prompts that signal "ready
for input" vs. pagination prompts that auto-scroll should handle:

1. **Navigation prompts** (wait for user input):
   - `Select ... Option:`
   - `Select ... NAME:`
   - `DEVICE:`
   - `//` (default value indicator at end of line)

2. **Login prompts** (handled by login flow):
   - `ACCESS CODE:`
   - `VERIFY CODE:`

3. **Pagination prompts** (handled by auto-scroll):
   - `Press RETURN to continue`
   - `'^' TO STOP`
   - `Press <RETURN> to continue`
   - `END OF REPORT!`

### Rationale
Patterns are derived from empirical observation of a VEHU
session and corroborated by MUMPS source code (GMTSUP.m for
pagination, ZU.m for login flow). The regex approach allows
users to extend or override patterns for site-specific VistA
configurations.

---

## 3. SSH Library Selection

### Decision
Use **paramiko** with a custom expect layer (~150 lines).

### Constitutional Tension
The constitution's Operational Standards table specifies
`pexpect` as the Terminal Protocol. However:

- `pexpect.spawn()` requires a Unix pty (`pty.fork()`) — fails
  on Windows.
- `pexpect.pxssh` shells out to the system `ssh` binary —
  violates FR-026 (pure-Python SSH, no system binary).
- The constitution's own Principle I states: "The suite MUST run
  identically on macOS, Linux, and Windows."

Principle I (a core principle) takes precedence over the
Operational Standards table (a configuration detail). The
constitution must be amended to replace `pexpect` with
`paramiko` in the Terminal Protocol row.

### Library Comparison

| Criterion | pexpect | paramiko | asyncssh | fabric |
|-----------|---------|----------|----------|--------|
| Windows | **NO** | YES | YES | YES |
| No system SSH | **NO** | YES | YES | YES |
| Expect-style API | Native | Manual | Manual | Poor |
| VT100 handling | Manual | Manual | Manual | N/A |
| Pure Python† | Yes | Yes | Yes | Yes |
| Matches FR-026 | **NO** | YES | YES | YES |
| Matches FR-027 | **NO** | YES | YES | YES |
| Async required | No | No | **YES** | No |

†All depend on `cryptography` which has compiled C extensions
but ships pre-built wheels for all platforms (universally
accepted as "pure-Python SSH").

### Custom Expect Layer Design

```python
class ExpectChannel:
    """pexpect-style interface over a paramiko Channel."""

    def expect(
        self,
        patterns: list[re.Pattern],
        timeout: float = 30.0,
        settle: float = 0.5,
    ) -> tuple[int, re.Match, str]:
        """Block until pattern matches after settle period."""

    def send(self, text: str) -> None:
        """Send text to the channel."""

    def sendline(self, text: str = "") -> None:
        """Send text followed by newline."""
```

This approach:
- Satisfies FR-026 (pure-Python SSH via paramiko)
- Satisfies FR-027 (cross-platform)
- Satisfies FR-029 (500ms settling delay built in)
- Is fully testable with mock channels (unit tests without SSH)
- Follows the same pattern as the RPC library (custom protocol
  layer over transport)

### Rationale
Paramiko is the de facto Python SSH standard (used by Ansible,
Fabric, etc.). A custom expect layer is ~150 lines of focused
code, tailored to VistA's specific prompt patterns and settling
delay requirements. This avoids fighting a general-purpose
library's assumptions.

### Alternatives Considered
- **pexpect**: Disqualified by FR-026 and FR-027 — requires
  Unix pty and system `ssh` binary.
- **pexpect.fdpexpect + paramiko**: Works on Unix but fails on
  Windows (`Channel.fileno()` raises `NotImplementedError`).
- **asyncssh**: Viable but forces async/await throughout,
  inconsistent with the synchronous RPC library.
- **fabric**: Designed for discrete commands, not interactive
  terminal sessions.

---

## 4. ZU.m Routine Analysis

### Decision
The ZU routine is the entry point for VistA Roll-and-Scroll
sessions. Understanding its flow informs the library's session
lifecycle design.

### Key Findings (from MUMPS source via MCP)

```mumps
ZU ;SF/RWF - For Cache and Open M! ;06/13/2006
 ;;8.0;KERNEL;**34,94,118,162,170,225,419**;Jul 10, 1995
 ;TIE ALL TERMINALS EXCEPT CONSOLE TO THIS ROUTINE!
EN N $ES,$ETRAP S $ETRAP="D ERR^ZU Q:$QUIT -9 Q"
 ...
 G ^XUS   ; → delegates to XUS for login
```

- ZU is a thin wrapper that sets up error trapping, checks
  available job slots, handles ShareLic for Telnet connections,
  then delegates to **^XUS** for the actual login flow.
- The comment "TIE ALL TERMINALS EXCEPT CONSOLE TO THIS
  ROUTINE!" confirms that this is the standard terminal entry
  point that `vehutied`'s login shell invokes.
- Error handling includes stack overflow protection and
  `%ZTER` error logging.

### Login Flow (XUS → XUSRB → Menu)
1. `^XUS` → prompts ACCESS CODE / VERIFY CODE
2. Authentication via `$$CHECKAV^XUS` — validates against
   `^VA(200,...)` (NEW PERSON file)
3. On success → sets DUZ, prompts for TERMINAL TYPE NAME
4. Terminal type selection → calls `^XUS2` for menu display
5. User's primary menu option determines the final prompt

---

## 5. VT100 Escape Sequence Handling

### Decision
Strip VT100/ANSI escape sequences from output using regex.
Full terminal emulation (via `pyte` or similar) is deferred
to a future iteration.

### Observed Sequences

| Sequence | Meaning | Source |
|----------|---------|--------|
| `\x1b[?1;2c` | Device Attributes response (VT100 with AVO) | After terminal type selection |
| `\x1b[H\x1b[J` | Cursor Home + Erase Display | Screen clear between menus |
| `\x1b[<n>;<m>H` | Cursor positioning | ScreenMan forms (out of scope) |

### Stripping Pattern
```python
ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z?]')
clean = ANSI_ESCAPE.sub('', raw_output)
```

### Rationale
For Roll-and-Scroll interactions, escape sequences are noise
that should be stripped for human-readable output. Full
terminal emulation (tracking cursor position, handling
ScreenMan forms) is explicitly out of scope per the spec.

### Alternatives Considered
- **pyte library** (pure-Python VT100 emulator): Would provide
  full screen-state tracking but adds complexity and a
  dependency that isn't justified for Roll-and-Scroll text
  extraction. Can be added later if ScreenMan support is needed.

---

## 6. Pagination Patterns (GMTSUP.m Analysis)

### Decision
The library recognises three primary pagination patterns with a
generous regex to handle site-specific variations.

### Source Analysis (GMTSUP.m)

The Health Summary pagination routine (`CKP^GMTSUP`) is
representative of VistA's pagination approach:

- Checks `$Y` (current line position) against `IOSL` (screen
  length) minus a footer margin
- When the page is full, writes a form feed (`@IOF`), displays
  a header, then pauses for user input
- The pause prompt text varies by package but follows common
  patterns

### Common Pagination Patterns (from source survey)

| Pattern | Source Routine | Example |
|---------|---------------|---------|
| `Press RETURN to continue` | Multiple packages | Standard VistA |
| `Press <RETURN> to continue` | Some packages | Angle-bracket variant |
| `'^' TO STOP` | Health Summaries | Combined with continue |
| `END OF REPORT! Press <RETURN>` | PSGWUTL1 | Report completion |
| `Type <Enter> to continue` | Some newer packages | Enter variant |
| `press RETURN to continue` | Case variations | Lowercase |

### Default Pagination Regex
```python
PAGINATION_PATTERNS = [
    re.compile(r'[Pp]ress\s+<?RETURN>?\s+to\s+continue', re.IGNORECASE),
    re.compile(r"'\^'\s+TO\s+STOP", re.IGNORECASE),
    re.compile(r'END OF REPORT', re.IGNORECASE),
    re.compile(r'[Tt]ype\s+<Enter>\s+to\s+continue', re.IGNORECASE),
]
```

---

## 7. VEHU Default Credentials

### Decision
Update the spec's default credentials to match the actual VEHU
container. The `SM1234`/`SM1234!!` combination referenced in the
RPC library spec is NOT available via Roll-and-Scroll login on
the current VEHU image.

### Observed Valid Credentials (from VEHU banner)

The VEHU container displays a credentials table at SSH login.
The safest default for smoke testing:

| User | Access Code | Verify Code | Role |
|------|-------------|-------------|------|
| PROGRAMMER,ONE | PRO1234 | PRO1234!! | Systems Manager (full access) |
| PROVIDER,VERO | CAS123 | CAS123.. | Clinical provider |

### Recommendation
The library should default to `PRO1234`/`PRO1234!!` for VistA
application login (PROGRAMMER,ONE), as this provides the
broadest menu access for testing. The `SM1234`/`SM1234!!`
credentials work for RPC Broker connections but are NOT valid
at the VistA Roll-and-Scroll ACCESS CODE prompt on the current
VEHU image.

### Environment Variables
- `VISTA_SSH_USER` / `VISTA_SSH_PASSWORD` → OS-level (default: `vehutied`/`tied`)
- `VISTA_ACCESS_CODE` / `VISTA_VERIFY_CODE` → VistA application (default: `PRO1234`/`PRO1234!!`)

---

## 8. Constitutional Amendment Required

### Decision
Amend the constitution's Operational Standards table to replace
`pexpect` with `paramiko` + custom expect layer.

### Proposed Change

| Component | Current | Proposed |
|-----------|---------|----------|
| **Terminal Protocol** | `pexpect` (over `telnetlib`) | `paramiko` with custom expect layer (over `pexpect`) |

### Rationale
- `pexpect` cannot satisfy Principle I (cross-platform) and
  FR-026 (no system binaries) simultaneously.
- Principle I is a Core Principle; the Operational Standards
  table is administrative configuration.
- Core Principles take precedence over operational details.
- `paramiko` satisfies the *intent* of the `pexpect` entry
  (interactive pty handling for VistA menus) while complying
  with the portability mandate.

### Impact
- No existing code uses `pexpect` (feature 002 hasn't been
  implemented yet).
- No breaking changes — this is a forward-looking amendment.
- The `pyproject.toml` dependency list will add `paramiko`
  instead of `pexpect`.

---

## 9. paramiko-expect Prior Art Review

### Source
[fgimian/paramiko-expect](https://github.com/fgimian/paramiko-expect/blob/master/paramiko_expect.py)
— unmaintained library providing an expect-style wrapper around
paramiko. Not suitable as a dependency but reviewed for design
insights relevant to our custom `ExpectChannel`.

### Patterns to Adopt

1. **Incremental UTF-8 decoding**: Uses
   `codecs.getincrementaldecoder(encoding)()` to handle
   multi-byte characters split across `recv()` calls. VistA can
   emit accented characters in patient names, and paramiko's
   `channel.recv()` returns raw bytes with no guarantee of
   character boundary alignment. Our `ExpectChannel` should use
   an incremental decoder rather than naive `bytes.decode()`.

2. **Carriage return stripping**: Strips `\r` from output
   before pattern matching (`buffer.replace('\r', '')`).
   Paramiko pty channels deliver `\r\n` line endings. Our VT100
   cleaning pipeline should strip `\r` as a first pass before
   ANSI escape removal.

3. **`send_ready()` guard**: Polls `channel.send_ready()`
   before calling `channel.send()`. Prevents blocking on a full
   send buffer. Low cost, worth including as defensive code.

4. **Command echo removal**: Saves the sent command string and
   strips it from captured output before returning. Our
   `CommandRecord.output` contract specifies "cleaned output
   between command echo and prompt" — this confirms we need
   explicit echo-stripping logic in the output cleaning path.

### Patterns to Deliberately Avoid

1. **No settling delay**: Matches as soon as regex hits the
   buffer. Our 500ms settle delay (FR-029) is critical for
   VistA, which sends output in bursts across multiple
   `recv()` calls. Premature matching on partial output is a
   known source of flaky test automation against VistA.

2. **`lines_to_check` windowing**: Only matches against the
   last N lines of output. Fragile for VistA prompts that may
   appear as inline single-line responses (e.g., `Select:`).
   Our approach of matching against the full accumulated buffer
   tail is more robust.

3. **`re.match` with anchored prefix/suffix**: Constructs
   `.*\n<regex>$` and uses `re.DOTALL`. Forces prompts to be
   line-anchored, which breaks for VistA inline prompts. Our
   `re.search` approach is more flexible.

4. **`socket.timeout`-based timeout**: Sets
   `channel.settimeout(timeout)` which raises `socket.timeout`
   from `recv()`. Conflates network failure with prompt-wait
   timeout. Our plan correctly uses a separate time-tracking
   loop with `recv_ready()` polling to distinguish connection
   loss from slow VistA output.

5. **Silent `-1` return on timeout**: Returns `-1` instead of
   raising an exception. Our `PromptTimeoutError` with
   `partial_output` attribute is far more debuggable.

6. **Incomplete ANSI regex**: Their `strip_ansi_codes` misses
   VT100 device attribute responses (`\x1b[?1049h`), cursor
   position requests (`\x1b[6n`), and cursor visibility
   sequences (`\x1b[?25l`) that VistA emits. Our regex
   (`\x1b\[[0-9;]*[a-zA-Z?]`) has broader coverage.

### Design Refinements for ExpectChannel

Based on this review, two internal implementation details are
added to the `ExpectChannel` design:

1. **Incremental decoder**: Use
   `codecs.getincrementaldecoder('utf-8')()` in the read loop
   rather than `bytes.decode('utf-8')` on each `recv()` chunk.

2. **Output cleaning pipeline** (applied in order):
   - Strip `\r` (pty line endings)
   - Strip VT100/ANSI escape sequences
   - Strip command echo
   - Result → `CommandRecord.output`

These are internal to `ExpectChannel` and do not change the
public API surface or data model.
