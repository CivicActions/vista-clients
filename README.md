# vista-test

A Python toolkit for programmatic interaction with VistA (Veterans Health Information Systems and Technology Architecture). Provides two complementary libraries for automated testing and integration:

| Package | Transport | Port | Use Case |
|---------|-----------|------|----------|
| `vista_test.rpc` | XWB wire protocol over TCP | 9430 | Invoke Remote Procedure Calls (RPCs) |
| `vista_test.terminal` | SSH interactive shell (paramiko) | 2222 | Drive Roll-and-Scroll menus, scrape screen output |

Both libraries are pure Python (3.10+), designed for the [WorldVistA VEHU](https://hub.docker.com/r/worldvista/vehu) Docker image, and follow a consistent credential-resolution pattern (explicit args → environment variables → VEHU defaults).

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [VistA VEHU Docker Setup](#vista-vehu-docker-setup)
- [Installation](#installation)
- [RPC Broker Library](#rpc-broker-library-vista_testrpc)
- [Terminal Library](#terminal-library-vista_testterminal)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)

---

## Prerequisites

- **Python 3.10+**
- **Docker** (for the VEHU VistA instance)
- **[uv](https://docs.astral.sh/uv/)** package manager (recommended)

---

## VistA VEHU Docker Setup

The [WorldVistA VEHU](https://hub.docker.com/r/worldvista/vehu) image provides a fully configured VistA instance with demonstration users, an RPC Broker listener on port 9430, and an SSH server on port 2222.

### Start VEHU

```bash
docker pull worldvista/vehu
docker run -d --name vehu -p 9430:9430 -p 2222:22 worldvista/vehu
```

Wait **~60 seconds** for the VistA environment to finish loading (the Broker listener and SSH daemon start after the MUMPS routines initialize).

### Verify It's Running

```bash
# Check RPC Broker listener (port 9430)
nc -z localhost 9430 && echo "RPC Broker is up"

# Check SSH (port 2222)
ssh -o StrictHostKeyChecking=no -p 2222 vehutied@localhost
# Password: tied
```

### Stop / Restart

```bash
docker stop vehu
docker start vehu    # data persists within the container
docker rm -f vehu    # destroy and re-create from image
```

### VEHU Default Credentials

| Level | Username / Code | Password / Code | Notes |
|-------|----------------|-----------------|-------|
| SSH (OS login) | `vehutied` | `tied` | Auto-launches VistA (`mumps -run ^ZU`) |
| SSH (programmer mode) | `vehuprog` | `prog` | Drops to MUMPS direct mode (`mumps -dir`) |
| VistA Application | `PRO1234` | `PRO1234!!` | PROGRAMMER,ONE — full system access |

> **Tip**: Use `vehutied` to land directly in the VistA Roll-and-Scroll environment. Use `vehuprog` for MUMPS direct/programmer mode.

Both libraries default to these credentials when no explicit values or environment variables are provided.

---

## Installation

```bash
cd vista-test
uv sync
```

This installs the `vista_test` package in development mode along with all dev dependencies (pytest, ruff, pyright, pytest-xdist).

---

## RPC Broker Library (`vista_test.rpc`)

A clean Pythonic API for the VistA XWB wire protocol. Handles TCP connection, XWB handshake, authentication (with dual cipher support), application context management, and RPC invocation.

### Quick Start

```python
from vista_test.rpc import VistABroker

with VistABroker("localhost", 9430) as broker:
    # Authenticate (uses VEHU defaults: PRO1234 / PRO1234!!)
    duz = broker.authenticate()
    print(f"Logged in as DUZ: {duz}")

    # Set application context
    broker.create_context("OR CPRS GUI CHART")

    # Call an RPC
    response = broker.call_rpc("ORWU USERINFO")
    print(response.value)
```

### Connection Lifecycle

The `VistABroker` context manager handles the full lifecycle: TCP connect → XWB handshake → ... → disconnect. You can also manage it manually:

```python
from vista_test.rpc import VistABroker

broker = VistABroker("localhost", 9430)
broker.connect()          # TCP + XWB handshake
broker.authenticate()     # XUS AV CODE
broker.create_context("OR CPRS GUI CHART")

response = broker.call_rpc("ORWU USERINFO")
print(response.value)

broker.disconnect()       # #BYE# + close socket
```

### RPC Parameters

```python
from vista_test.rpc import VistABroker, literal, list_param

with VistABroker("localhost", 9430) as broker:
    broker.authenticate()
    broker.create_context("OR CPRS GUI CHART")

    # No parameters
    response = broker.call_rpc("ORWU USERINFO")

    # Literal (string) parameter
    response = broker.call_rpc("XWB GET VARIABLE VALUE", [literal("DUZ")])
    print(f"DUZ = {response.value}")

    # List (key-value) parameter — must be last in the parameter list
    response = broker.call_rpc("MY RPC", [
        literal("some_value"),
        list_param({"NAME": "DOE,JOHN", "SSN": "000123456"}),
    ])
    print(response.lines)
```

### Response Handling

```python
response = broker.call_rpc("ORWU USERINFO")

# Single-value response
print(response.value)       # "12345^DOE,JOHN^..."

# Array/multi-line response
print(response.lines)       # ["line1", "line2", ...]
print(response.is_array)    # True if lines is populated

# Raw server response (before parsing)
print(response.raw)
```

### Custom Credentials

```python
# Explicit arguments
with VistABroker("my-vista-server", 9430) as broker:
    broker.authenticate(access_code="MYACCESS", verify_code="MYVERIFY1!")

# Environment variables (see Environment Variables section)
# export VISTA_ACCESS_CODE=MYACCESS
# export VISTA_VERIFY_CODE=MYVERIFY1!
with VistABroker("my-vista-server", 9430) as broker:
    broker.authenticate()  # picks up env vars automatically
```

### Keepalive

```python
with VistABroker("localhost", 9430) as broker:
    broker.authenticate()
    broker.create_context("OR CPRS GUI CHART")

    for batch in work_batches:
        process(batch)
        broker.ping()  # XWB IM HERE — resets server's 3-minute timeout
```

### Error Handling

```python
from vista_test.rpc import VistABroker
from vista_test.rpc.errors import (
    ConnectionError,
    HandshakeError,
    AuthenticationError,
    ContextError,
    RPCError,
    StateError,
)

try:
    with VistABroker("localhost", 9430) as broker:
        broker.authenticate()
        broker.create_context("OR CPRS GUI CHART")
        response = broker.call_rpc("SOME RPC")
except ConnectionError as e:
    print(f"Cannot reach server: {e}")
except HandshakeError as e:
    print(f"XWB handshake rejected: {e}")
except AuthenticationError as e:
    print(f"Bad credentials: {e}")
except ContextError as e:
    print(f"Context not available: {e}")
except RPCError as e:
    print(f"RPC failed: {e}")
except StateError as e:
    print(f"Wrong session state: {e}")
```

### API Reference

| Class / Function | Description |
|-----------------|-------------|
| `VistABroker(host, port, *, timeout, app_name, cipher)` | RPC Broker client with context manager support |
| `broker.connect()` | TCP connect + XWB handshake |
| `broker.authenticate(access_code, verify_code)` | Login, returns DUZ string |
| `broker.create_context(option_name)` | Set B-type application context |
| `broker.call_rpc(rpc_name, params)` | Invoke RPC, returns `RPCResponse` |
| `broker.ping()` | Send XWB IM HERE keepalive |
| `broker.disconnect()` | Send #BYE# and close connection |
| `broker.is_connected` | Connection status (bool) |
| `broker.duz` | Authenticated user's DUZ or None |
| `broker.state` | Current `SessionState` enum value |
| `literal(value)` | Create a literal (string) RPC parameter |
| `list_param(entries)` | Create a list (key-value) RPC parameter |
| `RPCResponse.value` | Single-value response string |
| `RPCResponse.lines` | Array response as list of strings |
| `RPCResponse.is_array` | Whether response is multi-valued |

---

## Terminal Library (`vista_test.terminal`)

An SSH-based interactive terminal driver for VistA's Roll-and-Scroll interface. Built on paramiko with a custom expect engine for prompt detection, pagination handling, and VT100 escape sequence stripping.

### Quick Start

```python
from vista_test.terminal import VistATerminal

with VistATerminal("localhost", 2222) as term:
    # login() handles ACCESS CODE + VERIFY CODE + terminal type
    term.login()

    # Send a command and wait for the next prompt
    output = term.send_and_wait("User Management")
    print(output)
```

### Connection Lifecycle

The `VistATerminal` context manager handles: SSH connect → OS login → VistA login → ... → disconnect. You can also manage each step:

```python
from vista_test.terminal import VistATerminal

term = VistATerminal("localhost", 2222)

# Step 1: SSH connect → OS login → arrive at ACCESS CODE prompt
banner = term.connect()       # SSH user: vehutied / tied
print(banner)

# Step 2: VistA application login
greeting = term.login()       # Access: PRO1234 / PRO1234!!
print(greeting)               # "Good evening DOCTOR"

# Step 3: Interact with menus
output = term.send_and_wait("Systems Manager Menu")
print(output)

# Step 4: Quit and disconnect
term.send_and_wait("Q")
term.disconnect()
```

### Custom Credentials

```python
# Explicit SSH + VistA credentials
term = VistATerminal("my-vista-server", 2222)
term.connect(ssh_user="myuser", ssh_password="mypass")
term.login(access_code="MYACC", verify_code="MYVER1!")

# Environment variables (see Environment Variables section)
# export VISTA_SSH_USER=myuser
# export VISTA_SSH_PASSWORD=mypass
# export VISTA_ACCESS_CODE=MYACC
# export VISTA_VERIFY_CODE=MYVER1!
with VistATerminal("my-vista-server", 2222) as term:
    term.login()  # picks up all env vars automatically
```

### Auto-Scroll (Pagination Handling)

VistA paginates long output with prompts like `Press RETURN to continue` or `'^' TO STOP`. Auto-scroll advances through these automatically:

```python
with VistATerminal("localhost", 2222) as term:
    term.login()

    # Enable auto-scroll for the session
    term.auto_scroll = True
    term.max_pages = 50           # safety limit (default: 100)

    output = term.send_and_wait("Long Report Option")
    print(output)                 # all pages captured

    # Or enable for a single command only
    term.auto_scroll = False
    output = term.send_and_wait(
        "Another Report",
        auto_scroll=True,
        max_pages=10,
    )
```

### Output Inspection

```python
with VistATerminal("localhost", 2222) as term:
    term.login()
    output = term.send_and_wait("ORWU PARAM")

    # Substring search on last command output
    if term.contains("PROVIDER"):
        print("Found PROVIDER in output")

    # Regex search
    match = term.search(r"DUZ=(\d+)")
    if match:
        print(f"DUZ: {match.group(1)}")

    # Full session history
    for record in term.session_history:
        print(f"[{record.timestamp:.0f}] {record.command}")
        print(f"  → {record.output[:80]}...")
```

### Waiting for Custom Prompts

```python
import re

with VistATerminal("localhost", 2222) as term:
    term.login()

    # Send raw text (no automatic newline wait)
    term.send("Special Menu Option\r")

    # Wait for a specific pattern
    match, text = term.wait_for(r"Enter your choice:")
    print(f"Prompt appeared, preceding text: {text}")

    # Respond
    output = term.send_and_wait("1")
```

### Error Handling

```python
from vista_test.terminal import VistATerminal
from vista_test.terminal.errors import (
    ConnectionError,
    AuthenticationError,
    SessionError,
    PromptTimeoutError,
    LoginPromptError,
    StateError,
)

try:
    with VistATerminal("localhost", 2222) as term:
        term.login()
        output = term.send_and_wait("Some Menu Option")
except ConnectionError as e:
    print(f"SSH connection failed: {e}")
except AuthenticationError as e:
    print(f"Bad credentials ({e.level} level): {e}")
except SessionError as e:
    print(f"VistA environment failed to load: {e}")
except LoginPromptError as e:
    print(f"Unexpected login prompt: {e.prompt_text}")
except PromptTimeoutError as e:
    print(f"Prompt timeout. Partial output: {e.partial_output[:200]}")
except StateError as e:
    print(f"Wrong session state: {e}")
```

### API Reference

| Class / Function | Description |
|-----------------|-------------|
| `VistATerminal(host, port, *, timeout, prompt_timeout, settle_delay, terminal_type)` | Terminal session driver with context manager |
| `term.connect(ssh_user, ssh_password)` | SSH connect + OS login, returns banner text |
| `term.login(access_code, verify_code)` | VistA application login, returns greeting |
| `term.send(text)` | Send raw text without waiting for a prompt |
| `term.send_and_wait(command, *, prompt, timeout, auto_scroll, max_pages)` | Send command and wait for next prompt, returns cleaned output |
| `term.wait_for(pattern, *, timeout)` | Wait for a regex match, returns `(match, text)` |
| `term.disconnect()` | Close SSH channel and transport |
| `term.last_output` | Cleaned output from last `send_and_wait()` |
| `term.raw_last_output` | Raw output (with escape sequences) from last call |
| `term.session_history` | List of `CommandRecord` objects since session start |
| `term.full_output` | All raw output since session start |
| `term.contains(text)` | Substring search on last cleaned output |
| `term.search(pattern)` | Regex search on last cleaned output |
| `term.is_connected` | Connection status (bool) |
| `term.state` | Current `SessionState` enum |
| `term.auto_scroll` | Get/set auto-scroll for pagination (default: `False`) |
| `term.max_pages` | Get/set page limit for auto-scroll (default: `100`) |
| `strip_escape_sequences(text)` | Remove VT100/ANSI escape codes from a string |
| `CommandRecord` | Dataclass: `command`, `output`, `raw_output`, `prompt`, `timestamp` |

---

## Running Tests

Tests are organized in three tiers:

| Tier | Directory | Server Required | What It Tests |
|------|-----------|-----------------|---------------|
| **Unit** | `tests/unit/` | No | Protocol encoding, cipher, state machine, mocks |
| **Contract** | `tests/contract/` | No | Wire format against known-good byte sequences |
| **Smoke** | `tests/smoke/` | Yes (VEHU) | Full lifecycle against a live VistA instance |

### Unit & Contract Tests (No Server)

```bash
# All offline tests
uv run pytest tests/unit/ tests/contract/ -v

# Run in parallel with pytest-xdist
uv run pytest tests/unit/ tests/contract/ -n auto
```

### Smoke Tests (Requires VEHU)

```bash
# Start VEHU first
docker run -d --name vehu -p 9430:9430 -p 2222:22 worldvista/vehu
sleep 60  # wait for VistA to initialize

# Run smoke tests
uv run pytest tests/smoke/ -v
```

### All Tests

```bash
uv run pytest -v
```

### Alpine Container Test

Verify the library runs in a minimal container with no development tools:

```bash
docker build -f Dockerfile.test -t vista-test-alpine .
docker run --rm vista-test-alpine
```

### Linting & Type Checking

```bash
# Lint and format check
uv run ruff check .
uv run ruff format --check .

# Type checking
uv run pyright
```

---

## Project Structure

```
vista-test/
├── pyproject.toml                      # Package config, dependencies, tool settings
├── Dockerfile.test                     # Alpine container verification
├── README.md
│
├── src/vista_test/
│   ├── __init__.py
│   ├── rpc/                            # RPC Broker library
│   │   ├── __init__.py                 # Public re-exports (15 symbols)
│   │   ├── broker.py                   # VistABroker lifecycle orchestrator
│   │   ├── protocol.py                 # XWB messages, S/L-PACK, cipher, response parsing
│   │   ├── transport.py                # TCP socket wrapper with chr(4) EOT framing
│   │   └── errors.py                   # VistAError exception hierarchy (7 classes)
│   └── terminal/                       # Terminal interaction library
│       ├── __init__.py                 # Public re-exports (11 symbols)
│       ├── session.py                  # VistATerminal session orchestrator
│       ├── expect.py                   # ExpectChannel: prompt matching over paramiko
│       ├── transport.py                # SSHTransport: paramiko SSH wrapper
│       ├── vt100.py                    # VT100/ANSI escape sequence stripping
│       └── errors.py                   # TerminalError exception hierarchy (7 classes)
│
├── tests/
│   ├── unit/                           # Offline tests — no server needed
│   │   ├── test_protocol.py            # XWB encoding, cipher, message format
│   │   ├── test_broker.py              # Broker state machine, credential resolution
│   │   ├── test_transport.py           # TCP transport with mocked sockets
│   │   ├── test_errors.py              # RPC exception hierarchy
│   │   ├── test_stdlib_only.py         # Verify RPC library uses only stdlib
│   │   ├── test_terminal_errors.py      # Terminal exception hierarchy
│   │   ├── test_terminal_expect.py     # ExpectChannel prompt matching
│   │   ├── test_session.py             # Terminal state machine, credentials
│   │   ├── test_terminal_transport.py  # SSHTransport with mocked paramiko
│   │   └── test_vt100.py              # Escape sequence stripping
│   ├── contract/                       # Wire format verification
│   │   ├── test_wire_format.py         # RPC known-good byte sequences
│   │   └── test_prompt_patterns.py     # Terminal prompt regex vs VEHU output
│   └── smoke/                          # Live server tests (requires VEHU)
│       ├── test_lifecycle.py           # RPC: connect → auth → RPC → disconnect
│       ├── test_quickstart.py          # RPC quickstart examples
│       └── test_terminal_lifecycle.py  # Terminal: SSH → login → command → disconnect
│
└── specs/                              # Feature specifications
    ├── 001-vista-rpc-library/
    │   ├── spec.md                     # User stories and acceptance criteria
    │   ├── research.md                 # XWB protocol analysis
    │   ├── plan.md                     # Architecture and tech stack
    │   ├── data-model.md               # Entity definitions
    │   ├── quickstart.md               # Usage examples
    │   ├── tasks.md                    # Implementation task breakdown
    │   ├── contracts/api.md            # Public API surface
    │   └── checklists/requirements.md  # Verification checklist
    └── 002-vista-terminal-library/
        ├── spec.md
        ├── research.md
        ├── plan.md
        ├── data-model.md
        ├── quickstart.md
        ├── tasks.md
        ├── contracts/api.md
        └── checklists/requirements.md
```

---

## Environment Variables

Both libraries share a consistent credential resolution order: **explicit arguments → environment variables → VEHU defaults**.

| Variable | Used By | Default | Description |
|----------|---------|---------|-------------|
| `VISTA_ACCESS_CODE` | rpc, terminal | `PRO1234` | VistA Access Code |
| `VISTA_VERIFY_CODE` | rpc, terminal | `PRO1234!!` | VistA Verify Code |
| `VISTA_SSH_USER` | terminal | `vehutied` | SSH username for terminal sessions |
| `VISTA_SSH_PASSWORD` | terminal | `tied` | SSH password for terminal sessions |

---

## License

See individual package files for license information.
